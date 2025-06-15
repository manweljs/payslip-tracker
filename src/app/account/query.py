
import strawberry
from app.account.models import User
from base.gql.register import register_query
from base.gql.types import Info
from sqlmodel.ext.asyncio.session import AsyncSession


@strawberry.type
class AccountQuery:
    @strawberry.field
    async def get_user(self, info: Info, email:str) -> str:
        db: AsyncSession = info.context.db
        user = await User.get_or_404(db, username=email)
        return user.id


register_query(AccountQuery)