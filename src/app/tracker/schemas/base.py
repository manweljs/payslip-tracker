from decimal import Decimal
from typing import Optional
from uuid import UUID
from datetime import datetime, date as datetime_date
from dataclasses import dataclass
from base.gql.schema import BaseDataModel

@dataclass
class BaseIncome(BaseDataModel):
    id: Optional[UUID] = None
    contact_id: Optional[UUID] = None
    amount: Optional[float] = None
    description: Optional[str] = None
    income_date: Optional[datetime] = None
    created_at: datetime = None
    updated_at: Optional[datetime] = None

