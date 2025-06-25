from datetime import datetime
from typing import List, Optional
from uuid import UUID
import strawberry
from app.account.models import Contact
from app.tracker.models import Income
from app.tracker.schemas.output import IncomeSchema
from base.gql.register import register_query
from base.gql.types import Info
from sqlmodel.ext.asyncio.session import AsyncSession

from base.model.filter import Q


@strawberry.type
class IncomeQuery:
    @strawberry.field
    async def get_income_by_id(self, info: Info,id:UUID, relations:Optional[List[str]]=None) -> IncomeSchema:
        db: AsyncSession = info.context.db
        income = await Income.get_or_404(db, id=id ,relations= relations);
        return await IncomeSchema.serialize(income,many=False)
    
    @strawberry.field
    async def get_all_income(self, info: Info, relations:Optional[List[str]]=None) -> List[IncomeSchema]:
        db: AsyncSession = info.context.db
        income = await Income.get_all(db, relations= relations);
        return await IncomeSchema.serialize(income,many=True)
    
    @strawberry.field
    async def search_income(self, info: Info,keyword: Optional[str] = None, relations:Optional[List[str]]=None) -> List[IncomeSchema]:
        db: AsyncSession = info.context.db
        income = await Income.search(db, 
                            keyword=keyword, 
                            search_fields=["description"],
                            relations=relations
                            )
        return await IncomeSchema.serialize(income,many=True)
    @strawberry.field
    async def filter_income(self, info: Info, id:Optional[UUID] = None,amount: Optional[str] = None, income_date: Optional[datetime] = None, relations: Optional[List[str]] = None ) -> List[IncomeSchema]:
        db: AsyncSession = info.context.db

        filters = {}
        if amount:
            filters['amount'] = amount
        if income_date:
            filters['income_date']= income_date
            if id:
                filters['id']=id
        income = await Income.filter(
            db, 
            relations=relations,
            order_by="amount", 
            **filters,
        )
        return await IncomeSchema.serialize(income, many=True)
    


register_query(IncomeQuery)