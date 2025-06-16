from typing import TYPE_CHECKING, List, Optional
from uuid import UUID, uuid4
from datetime import datetime, timedelta

from sqlalchemy import table
from sqlmodel import Field, Relationship, SQLModel
from base.model import BaseModel

if TYPE_CHECKING:
    from app.tracker.models import Income

class ContactConfig(BaseModel, table=True):
    __tablename__ = "ContactConfig"

    id: Optional[UUID] = Field(
        default_factory=uuid4,
        primary_key=True,
        sa_column_kwargs={"name": "ContactConfigID"}
    )
    contact_id: Optional[UUID] = Field(
        foreign_key="Contact.ContactID",
        sa_column_kwargs={"name": "ContactID"},
        index=True
    )

    # Relationships
    contact: Optional["Contact"] = Relationship(back_populates="config", sa_relationship_kwargs={"uselist": False})



class Contact(BaseModel, table=True):
    __tablename__ = "Contact"

    id: Optional[UUID] = Field(
        default_factory=uuid4,
        primary_key=True,
        sa_column_kwargs={"name": "ContactID"}
    )
    first_name: Optional[str] = Field(
        max_length=50,
        sa_column_kwargs={"name": "FirstName"}
    )
    last_name: Optional[str] = Field(
        max_length=50,
        sa_column_kwargs={"name": "LastName"}
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        sa_column_kwargs={"name": "CreatedAt"}
    )
    updated_at: Optional[datetime] = Field(
        default_factory=datetime.now,
        sa_column_kwargs={"name": "UpdatedAt", "onupdate" : datetime.now()}
    )

    # Relationships
    user: Optional["User"] = Relationship(back_populates="contact", sa_relationship_kwargs={"uselist": False})
    incomes: Optional[List["Income"]] = Relationship(back_populates="contact")
    config: Optional["ContactConfig"] = Relationship(back_populates="contact", sa_relationship_kwargs={"uselist": False})



class User(BaseModel, table=True):
    __tablename__ = "User"

    id: Optional[UUID] = Field(
        default_factory=uuid4,
        primary_key=True,
        sa_column_kwargs={"name": "UserID"}
    )
    contact_id: Optional[UUID] = Field(
        foreign_key="Contact.ContactID",
        sa_column_kwargs={"name": "ContactID"},
        index=True
    )
    username: Optional[str] = Field(
        max_length=255,
        sa_column_kwargs={"name": "Username"},
    )
    password: Optional[str] = Field(
        max_length=255,
        sa_column_kwargs={"name": "Password"},
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        sa_column_kwargs={"name": "CreatedAt", }
    )
    updated_at: Optional[datetime] = Field(
        default_factory=datetime.now,
        sa_column_kwargs={"name": "UpdatedAt", "onupdate": datetime.now()}
    )

    # Relationships
    contact: Optional[Contact] = Relationship(back_populates="user", sa_relationship_kwargs={"uselist": False})


from app.tracker.models import Income
