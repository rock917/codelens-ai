from datetime import datetime, timezone
import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import AuthUser, get_current_user, owned_conversation, owned_repository
from app.database.base import get_db, AsyncSessionLocal
from app.models.repository import RepositoryJob
from app.models.conversation import Conversation, Message
from app.schemas.chat import ChatRequest, ChatResponse, SourceReference, ConversationUpdate
from app.services.rag.rag_engine import ask_question, stream_question

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)
ACTIVE = ('PENDING', 'RUNNING')


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def job_type(conversation_id):
    return f'CHAT:{conversation_id}'


async def active_reply(db, conversation_id):
    return await db.scalar(select(RepositoryJob.id).where(
        RepositoryJob.job_type == job_type(conversation_id), RepositoryJob.status.in_(ACTIVE),
    ).limit(1))


async def history_rows(db, conversation_id):
    return (await db.scalars(select(Message).where(Message.conversation_id == conversation_id)
                            .order_by(Message.created_at, Message.role.desc(), Message.id))).all()


async def finish_reply(db, conv_id, job_id, answer, sources):
    # A completed answer and its job status become visible together.
    message = Message(id=str(uuid.uuid4()), conversation_id=conv_id, role='assistant',
                      content=answer, sources=json.dumps(sources), created_at=now())
    db.add(message)
    conv = await db.get(Conversation, conv_id)
    job = await db.get(RepositoryJob, job_id)
    if conv is None or job is None:
        raise ValueError('Conversation removed during generation')
    conv.updated_at = now()
    job.status = 'COMPLETED'
    job.progress = 100
    await db.commit()
    return message.id


async def fail_reply(job_id):
    async with AsyncSessionLocal() as db:
        job = await db.get(RepositoryJob, job_id)
        if job and job.status in ACTIVE:
            job.status = 'FAILED'
            job.error_message = 'Reply interrupted or failed. The question is saved; no incomplete answer was saved.'
            await db.commit()


@router.post('')
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db),
               user: AuthUser = Depends(get_current_user)):
    repo = await owned_repository(db, request.repository_id, user.id)
    if repo.status != 'READY':
        raise HTTPException(400, 'Repository is not ready')
    if request.conversation_id:
        await owned_conversation(db, request.conversation_id, user.id)
        conv = await db.scalar(select(Conversation).where(
            Conversation.id == request.conversation_id,
            Conversation.repository_id == request.repository_id,
        ).with_for_update())
        if conv is None:
            raise HTTPException(404, 'Conversation not found')
        if await active_reply(db, conv.id):
            raise HTTPException(409, 'A reply is already being generated in this conversation. Reopen it to see the result.')
    else:
        conv = Conversation(id=str(uuid.uuid4()), repository_id=repo.id,
                            title=request.question[:80], created_at=now(), updated_at=now())
        db.add(conv)
        await db.flush()
    history = [{'role': m.role, 'content': m.content} for m in await history_rows(db, conv.id)]
    conv_id = conv.id
    question = Message(id=str(uuid.uuid4()), conversation_id=conv_id, role='user',
                       content=request.question, created_at=now())
    job = RepositoryJob(id=str(uuid.uuid4()), repository_id=repo.id,
                        job_type=job_type(conv_id), status='RUNNING', created_at=now())
    db.add_all([question, job])
    conv.updated_at = now()
    await db.commit()  # The question survives provider failures, disconnects and restarts.
    job_id, question_id = job.id, question.id
    meta = {'type': 'meta', 'conversation_id': conv_id, 'question_id': question_id}

    if request.stream:
        async def generate():
            # Streaming owns its session rather than depending on request cleanup timing.
            completed = False
            try:
                yield f'data: {json.dumps(meta)}\n\n'
                async with AsyncSessionLocal() as stream_db:
                    answer, sources = '', []
                    async for token, refs in stream_question(
                        repository_id=request.repository_id, question=request.question,
                        db=stream_db, conversation_history=history,
                    ):
                        answer += token
                        sources = refs
                        yield f'data: {json.dumps({"type": "token", "content": token})}\n\n'
                    if not answer.strip():
                        raise ValueError('Empty answer')
                    sources = [SourceReference(**source).model_dump() for source in sources]
                    message_id = await finish_reply(stream_db, conv_id, job_id, answer, sources)
                    completed = True
                yield f'data: {json.dumps({"type": "sources", "sources": sources})}\n\n'
                yield f'data: {json.dumps({"type": "done", "message_id": message_id})}\n\n'
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception('Chat reply failed for job %s', job_id)
                await fail_reply(job_id)
                yield f'data: {json.dumps({"type": "error", "message": "Your question was saved, but the reply failed. Please try again."})}\n\n'
            finally:
                if not completed:
                    await asyncio.shield(fail_reply(job_id))
        return StreamingResponse(generate(), media_type='text/event-stream',
                                 headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})
    try:
        answer, sources = await ask_question(repository_id=request.repository_id,
                                            question=request.question, db=db,
                                            conversation_history=history)
        if not answer.strip():
            raise ValueError('Empty answer')
        # Validate before committing a response that the API cannot serialize.
        references = [SourceReference(**source) for source in sources]
        message_id = await finish_reply(db, conv_id, job_id, answer, sources)
    except asyncio.CancelledError:
        await db.rollback()
        await asyncio.shield(fail_reply(job_id))
        raise
    except Exception:
        await db.rollback()
        await fail_reply(job_id)
        logger.exception('Chat reply failed for job %s', job_id)
        raise HTTPException(502, 'Your question was saved, but the reply failed. Reopen the conversation to try again.')
    return ChatResponse(conversation_id=conv_id, message_id=message_id, answer=answer,
                        sources=references, repository_id=request.repository_id)


@router.get('/conversations/{repository_id}')
async def get_conversations(repository_id: str, db: AsyncSession = Depends(get_db),
                            user: AuthUser = Depends(get_current_user)):
    await owned_repository(db, repository_id, user.id)
    rows = (await db.scalars(select(Conversation).where(Conversation.repository_id == repository_id)
                            .order_by(Conversation.updated_at.desc(), Conversation.id))).all()
    running = set((await db.scalars(select(RepositoryJob.job_type).where(
        RepositoryJob.repository_id == repository_id, RepositoryJob.status.in_(ACTIVE),
    ))).all())
    return [dict(id=c.id, repository_id=c.repository_id, title=c.title,
                 created_at=c.created_at, updated_at=c.updated_at,
                 is_generating=job_type(c.id) in running) for c in rows]


@router.get('/history/{conversation_id}')
async def get_history(conversation_id: str, db: AsyncSession = Depends(get_db),
                      user: AuthUser = Depends(get_current_user)):
    await owned_conversation(db, conversation_id, user.id)
    result = []
    for message in await history_rows(db, conversation_id):
        try:
            sources = json.loads(message.sources) if message.sources else []
        except (ValueError, TypeError):
            sources = []
        result.append(dict(id=message.id, role=message.role, content=message.content,
                           sources=sources, created_at=message.created_at))
    return result


@router.patch('/conversations/{conversation_id}')
async def rename_conversation(conversation_id: str, request: ConversationUpdate,
                              db: AsyncSession = Depends(get_db), user: AuthUser = Depends(get_current_user)):
    conv = await owned_conversation(db, conversation_id, user.id)
    conv.title = request.title
    conv.updated_at = now()
    await db.commit()
    return {'id': conv.id, 'title': conv.title}


@router.delete('/conversations/{conversation_id}', status_code=204)
async def delete_conversation(conversation_id: str, db: AsyncSession = Depends(get_db),
                              user: AuthUser = Depends(get_current_user)):
    await owned_conversation(db, conversation_id, user.id)
    conv = await db.scalar(select(Conversation).where(Conversation.id == conversation_id).with_for_update())
    if conv is None:
        raise HTTPException(404, 'Conversation not found')
    if await active_reply(db, conversation_id):
        raise HTTPException(409, 'Wait for the current reply to finish before deleting this conversation.')
    await db.execute(delete(Message).where(Message.conversation_id == conversation_id))
    await db.execute(delete(RepositoryJob).where(RepositoryJob.job_type == job_type(conversation_id)))
    await db.execute(delete(Conversation).where(Conversation.id == conversation_id))
    await db.commit()
    return Response(status_code=204)
