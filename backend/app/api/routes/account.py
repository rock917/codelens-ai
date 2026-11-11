from fastapi import APIRouter, Depends
from app.auth import AuthUser, get_current_user

router = APIRouter(prefix='/account', tags=['account'])


@router.get('/me')
async def account(user: AuthUser = Depends(get_current_user)):
    return {'id': user.id, 'email': user.email}
