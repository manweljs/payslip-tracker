
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException
import firebase_admin
from firebase_admin import credentials,auth
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from app.account.schemas.rest import ContactSchema, LoginRequest, LoginResponse, UserSchema
from config.db import get_db
from .models import User, Contact
from datetime import datetime
from pydantic import BaseModel
import pyrebase


import os

FIREBASE_CREDENTIALS = {
  "type": os.getenv("FIREBASE_TYPE"),
  "project_id": os.getenv("FIREBASE_PROJECT_ID"),
  "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
  "private_key": os.getenv("FIREBASE_PRIVATE_KEY"),
  "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
  "client_id": os.getenv("FIREBASE_CLIENT_ID"),
  "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
  "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
  "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
  "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL"),
  "universe_domain": os.getenv("FIREBASE_UNIVERSE_DOMAIN")
}

firebase_config = {
    "apiKey": os.getenv("FIREBASE_APIKEY"),
    "authDomain": os.getenv("FIREBASE_AUTHDOMAIN"),
    "databaseURL": os.getenv("FIREBASE_DATABASEURL"),
    "storageBucket": os.getenv("FIREBASE_STORAGEBUCKET"),
}



cred = credentials.Certificate(FIREBASE_CREDENTIALS)
app = firebase_admin.initialize_app(cred)
firebase = pyrebase.initialize_app(firebase_config)
pyrebase_auth = firebase.auth()

router = APIRouter(prefix="/api/Account", tags=["Account"])

# Pyrebase config for client-side authentication





@router.post("/CreateUser")
async def create_user(
        first_name: str,
        last_name: str,
        username: str,
        password: str,
        db: AsyncSession = Depends(get_db),
    ):

    userfirebase = auth.create_user(
        email=username,
        password=password
    )

    contact = Contact(first_name=first_name, last_name=last_name)
    await contact.save(db, commit=False)

    user = User(username=username, password=password, contact_id=contact.id,firebase_uid =userfirebase.uid)
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

@router.post("/LoginUser", response_model=LoginResponse)
async def login_user(request: LoginRequest):
    try:
        user = pyrebase_auth.sign_in_with_email_and_password(request.email, request.password)
        return LoginResponse(
            idToken=user["idToken"],
            refreshToken=user["refreshToken"],
            expiresIn=user["expiresIn"],
            email=user["email"]
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid email or password")