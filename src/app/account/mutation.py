import logging
from typing import Optional
from fastapi import HTTPException
from firebase_admin import auth

import strawberry
from app.account.schemas.input import ContactInput, ContactNameInput
from app.account.schemas.output import LoginResponseType
from app.account.schemas.rest import LoginResponse
from base.gql.register import register_mutation, register_query, register_subscription
from base.gql.types import Info
from .models import Contact, User
import pyrebase
from app.account.routers import firebase_config 
logger =logging.getLogger(__name__)

firebase = pyrebase.initialize_app(firebase_config)
pyrebase_auth = firebase.auth()



@strawberry.type
class AccountMutation:
    @strawberry.mutation
    async def create_user(self, info: Info, data: Optional[ContactNameInput] = None)-> str:
        db = info.context.db
        
        userfirebase = auth.create_user(
                email=data.email,
                password=data.password
            )


        contact =  Contact(
            first_name=data.first_name,
            last_name=data.last_name
        )
        await contact.save(db)

        user = User(username=data.email, password=data.password, contact_id=contact.id,firebase_uid =userfirebase.uid)
        await user.save(db)

        return "Ok"
    
    @strawberry.mutation
    async def update_contact(self, info: Info, data: Optional[ContactNameInput] = None)-> str:
        db = info.context.db
        
        contact = await Contact.get_or_404(db, id=data.id, relations=["user"])

        contact.first_name = data.first_name
        contact.last_name = data.last_name
        await contact.save(db)

        logger.info(f"Updated contact: {contact.id} - {contact.first_name} {contact.last_name}")

        return f"Updated contact: {contact.id} - {contact.first_name} {contact.last_name}"

    @strawberry.mutation
    async def login_user(self, email: str, password: str) -> LoginResponseType:
        user = pyrebase_auth.sign_in_with_email_and_password(email, password)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        return LoginResponseType(
            idToken=user["idToken"],
            refreshToken=user["refreshToken"],
            expiresIn=user["expiresIn"],
            email=user["email"]
        )

register_mutation(AccountMutation)


