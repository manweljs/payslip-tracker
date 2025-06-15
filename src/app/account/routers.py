from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from config.db import get_db

router = APIRouter(prefix="/api/Account", tags=["Account"])

@router.get("/")
async def get_all_contact(
    db: AsyncSession = Depends(get_db)
):
    return {"message": "Welcome to the Account API!"}