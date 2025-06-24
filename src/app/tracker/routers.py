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

