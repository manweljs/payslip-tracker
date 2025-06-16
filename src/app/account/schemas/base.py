from decimal import Decimal
from typing import Optional
from uuid import UUID
from datetime import datetime, date as datetime_date
from dataclasses import dataclass
from base.gql.schema import BaseDataModel

@dataclass
class BaseContactConfig(BaseDataModel):
    id: Optional[UUID] = None
    contact_id: Optional[UUID] = None

@dataclass
class BaseContact(BaseDataModel):
    id: Optional[UUID] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    created_at: datetime = None
    updated_at: Optional[datetime] = None

@dataclass
class BaseUser(BaseDataModel):
    id: Optional[UUID] = None
    contact_id: Optional[UUID] = None
    username: Optional[str] = None
    password: Optional[str] = None
    created_at: datetime = None
    updated_at: Optional[datetime] = None

