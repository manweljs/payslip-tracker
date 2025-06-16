
from typing import List, Optional
import strawberry
from app.account.models import Contact, User
from app.account.schemas.output import ContactSchema
from base.gql.register import register_query
from base.gql.types import Info
from sqlmodel.ext.asyncio.session import AsyncSession


@strawberry.type
class AccountQuery:
    @strawberry.field
    async def search_contact(self, info: Info, keyword: Optional[str] = None, rels: Optional[List[str]]=None) -> List[ContactSchema]:
        db: AsyncSession = info.context.db
        contacts = await Contact.search(db, 
                            keyword=keyword, 
                            search_fields=["first_name", "last_name"],
                            relations=rels
                            )
        return await ContactSchema.serialize(contacts, many=True)


register_query(AccountQuery)