from datetime import datetime
from typing import Optional
from uuid import UUID
from base.gql.types import BaseGraphQLInput


class IncomeInput(BaseGraphQLInput):
    id: Optional[UUID] = None
    contact_id: Optional[UUID] = None
    amount: Optional[float] = None
    description: Optional[str] = None
    income_date: Optional[datetime] = None
    

class GoalInput(BaseGraphQLInput):
    contact_id: Optional[UUID] = None
    target_amount: Optional[float] = None
    description: Optional[str] = None
    target_date: Optional[datetime] = None
    