

from typing import Optional
from app.account.schemas.base import BaseContact, BaseUser
from base.gql.types import BaseGraphQLSchema
import strawberry

class UserSchema(BaseGraphQLSchema, BaseUser):
    pass

class ContactSchema(BaseGraphQLSchema, BaseContact):
    user : Optional[UserSchema] = None

@strawberry.type
class LoginResponseType:
    idToken: str
    refreshToken: str
    expiresIn: str
    email: str