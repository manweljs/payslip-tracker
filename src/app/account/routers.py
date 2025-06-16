from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter
from sqlalchemy import false
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from app.account.schemas.rest import ContactSchema, UserSchema
from config.db import get_db
from .models import User, Contact, ContactConfig
from datetime import datetime

router = APIRouter(prefix="/api/Account", tags=["Account"])

@router.post("/CreateUser")
async def create_user(
        first_name: str,
        last_name: str,
        username: str,
        password: str,
        db: AsyncSession = Depends(get_db),
    ):

    contact = Contact(first_name=first_name, last_name=last_name)
    await contact.save(db, commit=False)

    user = User(username=username, password=password, contact_id=contact.id)
    await user.save(db, commit=False)

    await db.commit()

    return {"message": "User created successfully", "user_id": str(user.id)}


@router.get("/GetContact")
async def get_contact(
    user_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    user = await User.get_or_404(db, id=user_id, relations=["contact"])
    if not user:
        raise ValueError("Contact not found")
    
    return user.contact


@router.get("/GetUser")
async def get_contact(
    contact_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    contact = await Contact.get_or_404(db, id=contact_id, relations=["user"])
    if not contact:
        raise ValueError("User not found")
    
    return contact.user




@router.get("/GetAllContacts",
response_model=List[ContactSchema],          
            )
async def get_all_contacts(
    db: AsyncSession = Depends(get_db)
):
    contacts = await Contact.search(db, relations=["user"])
    results = []
    
    for contact in contacts:
        result = ContactSchema(
            **contact.model_dump(),
            user=UserSchema(
                **contact.user.model_dump()
            )
        )
        results.append(result)

    return results



@router.get("/SearchContact",
response_model=List[ContactSchema],
            )
async def search_contact(
    keyword: str = None,
    fields: str = None,
    db: AsyncSession = Depends(get_db)
):
    fields = fields.split(",") if fields else ["first_name", "last_name"]

    query = await Contact.search(
        db, 
        keyword=keyword,
        search_fields=fields,
        relations=["user"]
     )

    results = []
    for contact in query:
        result = ContactSchema(
            **contact.model_dump(),
            user=UserSchema(
                **contact.user.model_dump()
            )
        )
        results.append(result)

    return results


@router.get("/FilterContacts")
async def filter_contacts(
    id: Optional[UUID] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    created_at: Optional[datetime] = None,
    updated_at: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db)
):
    
    filters = {}

    if id:
        filters['id'] = id

    if first_name:
        filters['first_name'] = first_name
    if last_name:
        filters['last_name'] = last_name

    if created_at:
        filters['created_at'] = created_at  
    if updated_at:
        filters['updated_at'] = updated_at

    query = await Contact.filter(
        db, 
        **filters,
        relations=["user"]
    )

    results = []
    for contact in query:
        result = ContactSchema(
            **contact.model_dump(),
            user=UserSchema(
                **contact.user.model_dump()
            )
        )
        results.append(result)

    return results