from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from config.db import get_db
from app.tracker.models import Income
from datetime import datetime
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
router = APIRouter(prefix="/api/Tracker", tags=["Tracker"])
@router.post("/CreateIncome")
async def create_income(
        contact_id: UUID,
        amount: float,
        description: str,
        income_date: datetime,
        db: AsyncSession = Depends(get_db),
    ):

    income = Income(contact_id=contact_id, amount=amount, description=description, income_date=income_date)
    await income.save(db, commit=False)

    await db.commit()

    return {"message": "User created successfully", "user_id": str(income.id)}


@router.get("/")
async def read_root():
    return {"message": "Welcome to the Payslip Tracker API!"}

