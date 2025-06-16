

from typing import Optional
from app.account.schemas.base import BaseContact, BaseUser
from base.gql.types import BaseGraphQLSchema

class UserSchema(BaseGraphQLSchema, BaseUser):
    pass

class ContactSchema(BaseGraphQLSchema, BaseContact):
    user : Optional[UserSchema] = None