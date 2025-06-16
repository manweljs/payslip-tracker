
from uuid import UUID
from pydantic import BaseModel

class UserSchema(BaseModel):
    id: UUID
    username: str


class ContactSchema(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    user: UserSchema
    
