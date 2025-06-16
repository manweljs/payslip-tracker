
from typing import Optional
from uuid import UUID
from app.account.schemas.base import BaseContact, BaseUser
from base.gql.types import BaseGraphQLInput


class UserInput(BaseGraphQLInput, BaseUser):
    pass

class ContactInput(BaseGraphQLInput, BaseContact):
    user: Optional[UserInput] = None

class ContactNameInput(BaseGraphQLInput):
    id: Optional[UUID] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None