import strawberry
from typing import List, Optional
from app.tracker.models import Goal
from app.tracker.schemas.base import BaseGoal
from app.tracker.schemas.output import GoalOutput
from base.gql.types import Info
from base.gql.register import register_query


@strawberry.type
class GoalQuery:
    @strawberry.field
    async def get_goal(self, info: Info, id: str) -> Optional[GoalOutput]:
        db = info.context.db
        goal = await Goal.get_or_404(db, id=id)
        if not goal:
            return None
        return GoalOutput(**goal.model_dump())

    @strawberry.field
    async def list_goals(self, info: Info) -> List[GoalOutput]:
        db = info.context.db
        goals = await Goal.search(db)
        return [GoalOutput(**g.model_dump()) for g in goals]


register_query(GoalQuery)
