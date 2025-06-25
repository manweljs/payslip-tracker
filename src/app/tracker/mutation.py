import logging
from typing import Optional
import strawberry
from app.tracker.schemas.input import IncomeInput
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

    
register_mutation(IncomeMutation)


