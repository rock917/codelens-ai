from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
import time
from app.auth import AuthUser, get_current_user
from app.database.base import AsyncSessionLocal
from app.models.deletion import AccountDeletion
from app.services.account_deletion import enabled, start_deletion

router = APIRouter(prefix='/account', tags=['account'])


@router.get('/export')
async def export_account(user: AuthUser = Depends(get_current_user)):
    from app.services.account_export import build_export
    return await build_export(user)


@router.get('/me')
async def account(user: AuthUser = Depends(get_current_user)):
    return {'id': user.id, 'email': user.email}


class DeleteConfirmation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirmation: str
    email: str


@router.get('/deletion')
async def deletion_status(user: AuthUser = Depends(get_current_user)):
    async with AsyncSessionLocal() as db:
        pending = await db.get(AccountDeletion, user.id) is not None
    return {'enabled': enabled(), 'pending': pending,
            'recent_sign_in': 0 <= time.time() - user.signed_in_at <= 600}


@router.delete('/deletion')
async def delete_account(body: DeleteConfirmation, user: AuthUser = Depends(get_current_user)):
    if body.confirmation != 'DELETE' or body.email.strip().casefold() != user.email.casefold():
        raise HTTPException(400, 'Type DELETE and confirm your account email.')
    if not 0 <= time.time() - user.signed_in_at <= 600:
        raise HTTPException(403, 'Sign in again, then return to Settings within 10 minutes.')
    complete = await start_deletion(user.id)
    return JSONResponse({'status': 'deleted' if complete else 'pending'}, status_code=200 if complete else 202)
