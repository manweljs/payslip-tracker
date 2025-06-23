from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship
from base.model import BaseModel
from app.account.models import Contact


class Income(BaseModel, table=True):
    __tablename__ = "Income"

    id: Optional[UUID] = Field(
        default_factory=uuid4, primary_key=True, sa_column_kwargs={"name": "IncomeID"}
    )
    contact_id: Optional[UUID] = Field(
        foreign_key="Contact.ContactID",
        sa_column_kwargs={"name": "ContactID"},
        index=True,
    )
    amount: Optional[float] = Field(sa_column_kwargs={"name": "Amount"})
    description: Optional[str] = Field(
        max_length=500, sa_column_kwargs={"name": "Description"}
    )
    income_date: Optional[datetime] = Field(sa_column_kwargs={"name": "IncomeDate"})
    created_at: datetime = Field(
        default_factory=datetime.now, sa_column_kwargs={"name": "CreatedAt"}
    )
    updated_at: Optional[datetime] = Field(
        default_factory=datetime.now,
        sa_column_kwargs={"name": "UpdatedAt", "onupdate": datetime.now()},
    )

    # Relationships
    contact: Optional[Contact] = Relationship(back_populates="incomes")


class Goal(BaseModel, table=True):
    __tablename__ = "Goal"

    id: Optional[UUID] = Field(
        default_factory=uuid4, primary_key=True, sa_column_kwargs={"name": "GoalID"}
    )
    contact_id: Optional[UUID] = Field(
        foreign_key="Contact.ContactID",
        sa_column_kwargs={"name": "ContactID"},
        index=True,
    )
    target_amount: Optional[float] = Field(sa_column_kwargs={"name": "TargetAmount"})
    description: Optional[str] = Field(
        max_length=500, sa_column_kwargs={"name": "Description"}
    )
    target_date: Optional[datetime] = Field(sa_column_kwargs={"name": "TargetDate"})
    created_at: datetime = Field(
        default_factory=datetime.now, sa_column_kwargs={"name": "CreatedAt"}
    )
    updated_at: Optional[datetime] = Field(
        default_factory=datetime.now,
        sa_column_kwargs={"name": "UpdatedAt", "onupdate": datetime.now()},
    )

    # Relationships
    contact: Optional[Contact] = Relationship(back_populates="goals")
