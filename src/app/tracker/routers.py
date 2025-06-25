from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from config.db import get_db
from datetime import datetime


@router.get("/")
async def read_root():
    return {"message": "Welcome to the Payslip Tracker API!"}

# --- GOAL CRUD ---

@router.post("/goals", response_model=dict)
async def create_goal(
    contact_id: UUID,
    target_amount: float,
    description: Optional[str] = None,
    target_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
):
    from .models import Goal
    goal = Goal(
        contact_id=contact_id,
        target_amount=target_amount,
        description=description,
        target_date=target_date,
    )
    await goal.save(db)
    return {"message": "Goal created successfully", "goal_id": str(goal.id)}

@router.get("/goals/{goal_id}", response_model=dict)
async def get_goal(goal_id: UUID, db: AsyncSession = Depends(get_db)):
    from .models import Goal
    goal = await Goal.get_or_404(db, id=goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal.model_dump()
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

@router.get("/goals", response_model=List[dict])
async def list_goals(db: AsyncSession = Depends(get_db)):
    from .models import Goal
    goals = await Goal.search(db)
    return [g.model_dump() for g in goals]

@router.put("/goals/{goal_id}", response_model=dict)
async def update_goal(
    goal_id: UUID,
    contact_id: Optional[UUID] = None,
    target_amount: Optional[float] = None,
    description: Optional[str] = None,
    target_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
):
    from .models import Goal
    goal = await Goal.get_or_404(db, id=goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    if contact_id is not None:
        goal.contact_id = contact_id
    if target_amount is not None:
        goal.target_amount = target_amount
    if description is not None:
        goal.description = description
    if target_date is not None:
        goal.target_date = target_date
    await goal.save(db)
    return {"message": "Goal updated successfully", "goal_id": str(goal.id)}

@router.delete("/goals/{goal_id}", response_model=dict)
async def delete_goal(goal_id: UUID, db: AsyncSession = Depends(get_db)):
    from .models import Goal
    goal = await Goal.get_or_404(db, id=goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    await goal.delete(db)
    return {"message": "Goal deleted successfully"}
router.post("/CreateIncome")
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



