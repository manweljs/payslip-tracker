from datetime import datetime
from uuid import UUID
import strawberry
from typing import Optional

@strawberry.type 
class GoalOutput:
       id: UUID
       contact_id: UUID
       target_amount: float
       description: str
       target_date: datetime
       created_at: datetime
       updated_at: Optional[datetime] = None

@strawberry.type
class IncomeOutput:
    id: UUID
    contact_id: UUID
    amount: float
    description: str
    income_date: datetime
    created_at: datetime
    updated_at: Optional[datetime] = None   