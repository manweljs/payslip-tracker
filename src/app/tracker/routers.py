from typing import List, Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.tracker.schemas.input import IncomeInput
from app.tracker.schemas.output import ContactIncomeSchema, IncomeSchema
from config.db import get_db
from app.tracker.models import Income

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
    return {"message": "Imcome created successfully", "income_id": str(income.id)}


@router.post("/UpdateIncome")
async def update_income(
    data: Optional[IncomeInput],
    db: AsyncSession = Depends(get_db),
):
    income = await Income.get_or_404(db, id=data.id)
    income.contact_id = data.contact_id
    income.amount = data.amount
    income.description = data.description
    income.income_date = data.income_date
    await income.save(db, commit=False)
    await db.commit()
    return {"message": "Updated successfully"}


@router.post("/DeleteIncome")
async def delete_income(
    id: Optional[UUID],
    db: AsyncSession = Depends(get_db),
):
    income = await Income.get_or_404(db, id=id)
    await income.delete(db, commit=False)
    await db.commit()
    return {"message": "Deleted successfully"}


@router.get("/GetIncomeByID")
async def get_income_by_id(
    id: UUID,
    db: AsyncSession = Depends(get_db)
):
    income = await Income.get_or_404(db, id=id, relations=["contact"])
    if not income:
        raise ValueError("Contact not found")
    return income


@router.get("/GetAllIncomes", response_model=List[IncomeSchema])
async def get_all_incomes(
    db: AsyncSession = Depends(get_db)
):
    imcomes = await Income.search(db, relations=["contact"])
    results = []
    for imcome in imcomes:
        result = IncomeSchema(
            **imcome.model_dump(),
            contact=ContactIncomeSchema(
                **imcome.contact.model_dump()
            )
        )
        results.append(result)
    return results


@router.get(
    "/SearchIncome",
    response_model=List[IncomeSchema],
)
async def search_income(
    keyword: str = None,
    db: AsyncSession = Depends(get_db)
):
    fields = ["description"]
    query = await Income.search(
        db,
        keyword=keyword,
        search_fields=fields,
        relations=["contact"]
    )
    results = []
    for imcome in query:
        result = IncomeSchema(
            **imcome.model_dump(),
            contact=ContactIncomeSchema(
                **imcome.contact.model_dump()
            )
        )
        results.append(result)
    return results


@router.get("/FilterIncomes")
async def filter_contacts(
    id: Optional[UUID] = None,
    amount: Optional[float] = None,
    income_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db)
):
    filters = {}
    if id:
        filters['id'] = id
    if amount:
        filters['amount'] = amount
    if income_date:
        filters['income_date'] = income_date
    query = await Income.filter(
        db,
        **filters,
        relations=["contact"]
    )
    results = []
    for income in query:
        result = IncomeSchema(
            **income.model_dump(),
            contact=ContactIncomeSchema(
                **income.contact.model_dump()
            )
        )
        results.append(result)
    return results

