import uuid
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.base import get_db
from app.models.repository import Repository
from app.models.conversation import Conversation, Message
from app.schemas.chat import ChatRequest, ChatResponse, SourceReference
from app.services.rag.rag_engine import ask_question, stream_question

router = APIRouter(prefix="/chat", tags=["chat"])

def generate_id() -> str:
    return str(uuid.uuid4())

async def get_or_create_conversation(
    db: AsyncSession,
    repository_id: str,
    conversation_id: str = None,
    title: str = None
) -> Conversation:
    if conversation_id:
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if conv:
            return conv

    conv = Conversation(
        id=generate_id(),
        repository_id=repository_id,
        title=title or "New Conversation"
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv

async def get_conversation_history(
    db: AsyncSession,
    conversation_id: str
) -> list:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()
    return [
        {"role": m.role, "content": m.content}
        for m in messages
    ]

@router.post("")
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    # Verify repository
    result = await db.execute(
        select(Repository).where(Repository.id == request.repository_id)
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(404, "Repository not found")
    if repo.status != "READY":
        raise HTTPException(400, f"Repository not ready. Status: {repo.status}")

    # Get or create conversation
    conv = await get_or_create_conversation(
        db=db,
        repository_id=request.repository_id,
        conversation_id=request.conversation_id,
        title=request.question[:50]
    )

    # Get history
    history = await get_conversation_history(db, conv.id)

    # Handle streaming
    if request.stream:
        async def generate():
            full_answer = ""
            sources = []
            first = True

            async for token, srcs in stream_question(
                repository_id=request.repository_id,
                question=request.question,
                db=db,
                conversation_history=history
            ):
                if first:
                    sources = srcs
                    # Send conversation_id first
                    yield f"data: {json.dumps({'type': 'meta', 'conversation_id': conv.id})}\n\n"
                    first = False

                full_answer += token
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

            # Save messages
            user_msg = Message(
                id=generate_id(),
                conversation_id=conv.id,
                role="user",
                content=request.question
            )
            db.add(user_msg)

            assistant_msg = Message(
                id=generate_id(),
                conversation_id=conv.id,
                role="assistant",
                content=full_answer,
                sources=json.dumps([s for s in sources])
            )
            db.add(assistant_msg)
            await db.commit()

            # Send sources at end
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no"
            }
        )

    # Non-streaming
    answer, sources = await ask_question(
        repository_id=request.repository_id,
        question=request.question,
        db=db,
        conversation_history=history
    )

    # Save messages
    user_msg = Message(
        id=generate_id(),
        conversation_id=conv.id,
        role="user",
        content=request.question
    )
    db.add(user_msg)

    msg_id = generate_id()
    assistant_msg = Message(
        id=msg_id,
        conversation_id=conv.id,
        role="assistant",
        content=answer,
        sources=json.dumps(sources)
    )
    db.add(assistant_msg)
    await db.commit()

    return ChatResponse(
        conversation_id=conv.id,
        message_id=msg_id,
        answer=answer,
        sources=[SourceReference(**s) for s in sources],
        repository_id=request.repository_id
    )

@router.get("/conversations/{repository_id}")
async def get_conversations(
    repository_id: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.repository_id == repository_id)
        .order_by(Conversation.created_at.desc())
    )
    return result.scalars().all()

@router.get("/history/{conversation_id}")
async def get_history(
    conversation_id: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()

    formatted = []
    for msg in messages:
        sources = []
        if msg.sources:
            try:
                sources = json.loads(msg.sources)
            except Exception:
                pass
        formatted.append({
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "sources": sources,
            "created_at": msg.created_at
        })
    return formatted