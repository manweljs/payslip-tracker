

from ast import List
import logging
from typing import Optional
from uuid import UUID
import strawberry
from app.account.models import Contact
from app.tracker.schemas.input import IncomeInput
from app.tracker.schemas.output import IncomeSchema
from base.gql.register import register_mutation, register_query, register_subscription
from base.gql.types import Info
from .models import Income

logger =logging.getLogger(__name__)

@strawberry.type
class IncomeMutation:
    @strawberry.mutation
    async def create_income(self, info: Info, data: Optional[IncomeInput] = None)-> str:
        db = info.context.db
        
        income =  Income(
            contact_id=data.contact_id,
            amount=data.amount,
            description=data.description,
            income_date=data.income_date,
        )
        await income.save(db)

        return "Ok"
    @strawberry.mutation
    async def update_income(self, info: Info, data: Optional[IncomeInput] = None)-> str:
        db = info.context.db
        
        income = await Income.get_or_404(db, id=data.id)

        income.contact_id = data.contact_id
        income.amount = data.amount
        income.description = data.description
        income.income_date = data.income_date
        await income.save(db)

        return f"Updated income successfully"

    
    @strawberry.mutation
    async def delete_income(self, info: Info, id: UUID)-> str:
        db = info.context.db
        
        income = await Income.get_or_404(db, id=id)
        await income.delete(db)

        return f"Deleted income successfully"
    
register_mutation(IncomeMutation)


