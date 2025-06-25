
from typing import Optional
from app.tracker.schemas.base import BaseIncome
from app.account.schemas.base import BaseContact
from base.gql.types import BaseGraphQLSchema

class ContactIncomeSchema(BaseGraphQLSchema, BaseContact):
    pass

class IncomeSchema(BaseGraphQLSchema, BaseIncome):
    contact : Optional[ContactIncomeSchema] = None
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