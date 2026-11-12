"""Verified Supabase identities and shared ownership checks.

Tokens are validated by the project's Auth server, never decoded without validation.
No service-role key or OAuth provider secret is needed here.
"""
from dataclasses import dataclass
from uuid import UUID
import base64
import json
import time

import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.models.repository import Repository, File
from app.models.conversation import Conversation

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str
    signed_in_at: float = 0


def verified_sign_in_time(token, user_id):
    # Called ONLY after Supabase validates this exact token. Never use iat: refresh
    # issues a new JWT without requiring the user to sign in again.
    try:
        payload = token.split('.')[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
        if claims.get('sub') != user_id:
            return 0
        timestamps = [entry['timestamp'] for entry in claims.get('amr', [])
                      if entry.get('method') in ('password', 'oauth')
                      and type(entry.get('timestamp')) in (int, float)
                      and 0 < entry['timestamp'] <= time.time() + 30]
        return max(timestamps, default=0)
    except (ValueError, KeyError, TypeError, IndexError, AttributeError):
        return 0


async def _fetch_user(token: str) -> httpx.Response:
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        return await client.get(
            f'{settings.SUPABASE_URL.rstrip("/")}/auth/v1/user',
            headers={'apikey': settings.SUPABASE_PUBLISHABLE_KEY, 'Authorization': f'Bearer {token}'},
        )


async def authenticate_token(token: str) -> AuthUser:
    if not settings.SUPABASE_URL or not settings.SUPABASE_PUBLISHABLE_KEY:
        raise HTTPException(503, 'Sign-in is not configured on this server')
    if not token or len(token) > 16384:
        raise HTTPException(401, 'Invalid access token', headers={'WWW-Authenticate': 'Bearer'})
    try:
        response = await _fetch_user(token)
    except httpx.RequestError:
        raise HTTPException(503, 'Sign-in verification is temporarily unavailable') from None
    if response.status_code == 429 or response.status_code >= 500:
        raise HTTPException(503, 'Sign-in verification is temporarily unavailable')
    if response.status_code != 200:
        raise HTTPException(401, 'Your session is invalid or expired', headers={'WWW-Authenticate': 'Bearer'})
    try:
        data = response.json()
        user_id = str(UUID(data['id']))
        email = data['email']
        if not isinstance(email, str) or not email:
            raise ValueError('Missing email')
    except (ValueError, KeyError, TypeError):
        raise HTTPException(401, 'Invalid account') from None
    if data.get('is_anonymous') or not data.get('email_confirmed_at'):
        raise HTTPException(403, 'Please confirm your email before continuing')
    return AuthUser(id=user_id, email=email, signed_in_at=verified_sign_in_time(token, user_id))


async def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> AuthUser:
    if credentials is None or credentials.scheme.lower() != 'bearer':
        raise HTTPException(401, 'Sign in to continue', headers={'WWW-Authenticate': 'Bearer'})
    user = await authenticate_token(credentials.credentials)
    from app.guards import check_account
    check_account(user.id, request.method, request.url.path)
    from app.services.account_deletion import account_work
    async with account_work(user.id, allow_deleting=request.url.path == '/account/deletion'):
        yield user


async def owned_repository(db: AsyncSession, repo_id: str, user_id: str) -> Repository:
    result = await db.execute(select(Repository).where(Repository.id == repo_id, Repository.owner_id == user_id))
    repo = result.scalar_one_or_none()
    if repo is None:
        # Do not reveal whether another user's repository exists.
        raise HTTPException(404, 'Repository not found')
    return repo


async def owned_file(db: AsyncSession, file_id: str, user_id: str, repo_id: str | None = None) -> File:
    query = select(File).join(Repository, File.repository_id == Repository.id).where(
        File.id == file_id, Repository.owner_id == user_id,
    )
    if repo_id is not None:
        query = query.where(File.repository_id == repo_id)
    file = (await db.execute(query)).scalar_one_or_none()
    if file is None:
        raise HTTPException(404, 'File not found')
    return file


async def owned_conversation(db: AsyncSession, conversation_id: str, user_id: str) -> Conversation:
    conversation = (await db.execute(
        select(Conversation).join(Repository, Conversation.repository_id == Repository.id).where(
            Conversation.id == conversation_id, Repository.owner_id == user_id,
        )
    )).scalar_one_or_none()
    if conversation is None:
        raise HTTPException(404, 'Conversation not found')
    return conversation
