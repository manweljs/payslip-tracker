

import strawberry

from base.gql.register import register_mutation
from base.gql.types import Info
from .models import User

@strawberry.type
class AccountMutation:

    @strawberry.mutation
    async def create_user(self, info: Info, email: str, password: str) -> str:
      
        db = info.context.db
        user = User(username=email, password=password)
        await user.save(db)

        return user.id
    
register_mutation(AccountMutation)