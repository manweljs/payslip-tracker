
from typing import Optional
from app.tracker.schemas.base import BaseIncome
from app.account.schemas.base import BaseContact
from base.gql.types import BaseGraphQLSchema

class ContactIncomeSchema(BaseGraphQLSchema, BaseContact):
    pass

class IncomeSchema(BaseGraphQLSchema, BaseIncome):
    contact : Optional[ContactIncomeSchema] = None