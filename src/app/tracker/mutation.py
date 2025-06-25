import logging
from typing import Optional
import strawberry
from app.tracker.schemas.input import GoalInput
from base.gql.register import register_mutation
from base.gql.types import Info
from .models import  Goal

logger =logging.getLogger(__name__)

@strawberry.type
class GoalMutation:
    @strawberry.mutation
    async def create_goal(self, info: Info, data: Optional[GoalInput] = None) -> str:
        db = info.context.db
        goal = Goal(
            contact_id=data.contact_id,
            target_amount=data.target_amount,
            description=data.description,
            target_date=data.target_date,
        )
        await goal.save(db)
        return "Ok"

    @strawberry.mutation
    async def update_goal(self, info: Info, id: str, data: GoalInput) -> str:
        db = info.context.db
        goal = await Goal.get_or_404(db, id=id)
        if data.contact_id is not None:
            goal.contact_id = data.contact_id
        if data.target_amount is not None:
            goal.target_amount = data.target_amount
        if data.description is not None:
            goal.description = data.description
        if data.target_date is not None:
            goal.target_date = data.target_date
        await goal.save(db)
        return "Ok"

    @strawberry.mutation
    async def delete_goal(self, info: Info, id: str) -> str:
        db = info.context.db
        goal = await Goal.get_or_404(db, id=id)
        await goal.delete(db)
        return "Ok"

register_mutation(GoalMutation)



