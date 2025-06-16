

import logging
from typing import Optional
import strawberry

from app.account.schemas.input import ContactInput, ContactNameInput
from base.gql.register import register_mutation, register_query, register_subscription
from base.gql.types import Info
from .models import Contact, User

logger =logging.getLogger(__name__)

@strawberry.type
class AccountMutation:
    @strawberry.mutation
    async def create_user(self, info: Info, data: Optional[ContactNameInput] = None)-> str:
        db = info.context.db
        
        contact =  Contact(
            first_name=data.first_name,
            last_name=data.last_name
        )
        await contact.save(db)

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

    
register_mutation(AccountMutation)


