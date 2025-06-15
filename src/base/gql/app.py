import inspect
from strawberry.fastapi import GraphQLRouter
from strawberry.fastapi import BaseContext
import os
from config.db import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request, Depends

from base.gql.register import build_schema
from utils.token import get_current_user
from strawberry.subscriptions import GRAPHQL_TRANSPORT_WS_PROTOCOL, GRAPHQL_WS_PROTOCOL

env = os.getenv("ENV", "DEV")


class ContextWrapper(BaseContext):
    def __init__(
        self, db: AsyncSession, request: Request = None, connection_params: dict = None
    ):
        self.db = db
        self.request = request
        self.connection_params = connection_params or {}
        self._user = None  # Cache for lazy user result
        self._partner = None  # Cache for partner
        self.operation_type = None
        # Make sure request is not None before accessing headers
        self.origin = request.headers.get("Origin") if request else None

    async def get_user(self):
        """
        Get user from the token in the connection_params or request headers.
        """
        if self._user is None:
            token = None

            # Get operation type directly from connection_params
            operation_type = (
                "subscription"
                if self.connection_params.get("operation") == "subscription"
                else "query/mutation"
            )

            self.operation_type = operation_type

            # Use token from the appropriate source
            if operation_type == "subscription":
                token = self.connection_params.get("Authorization")
                if token and token.startswith("Bearer "):
                    token = token.split(" ")[1]

            elif operation_type == "query/mutation":
                # Check first if request is available
                if self.request:
                    raw_token = self.request.headers.get("Authorization")
                    if raw_token and raw_token.startswith("Bearer "):
                        token = raw_token.split(" ")[1]

            if not token:
                raise ValueError("Authorization token is missing")

            # Validate token
            self._user = await get_current_user(token=token, db=self.db)

        return self._user

    @property
    async def user(self):
        return await self.get_user()

    async def get_partner(self):
        """
        Get partner from the public key or subdomain in the connection_params.
        """
        if self._partner is None:
            public_key = None
            subdomain = None
            # Check if request is available before accessing headers
            if self.request:
                public_key = self.request.headers.get("X-PARTNER-PUBLIC-KEY")
                subdomain = self.request.headers.get("X-PARTNER-SUBDOMAIN")

            if not subdomain and not public_key:
                return None

            filters = {}

            if subdomain:
                # If available in cache, it will be taken directly from cache and returned
                filters["subdomain"] = subdomain
            elif public_key:
                # If available in cache, it will be taken directly from cache and returned
                filters["public_key"] = public_key

            partner = None

            self._partner = partner

        return self._partner

    @property
    async def partner(self):
        return await self.get_partner()


# context_getter function to provide ContextWrapper
async def context_getter(
    db: AsyncSession = Depends(get_db),
    request: Request = None,
    connection_params: dict = None,
) -> ContextWrapper:

    return ContextWrapper(db=db, request=request, connection_params=connection_params)


from strawberry.exceptions import UnresolvedFieldTypeError

try:
    schema = build_schema()
except UnresolvedFieldTypeError as e:
    td = e.type_definition
    # GraphQL type name
    print(">>> GraphQL type   :", td.name)
    # Original Python class (origin)
    py_cls = getattr(td, "origin", None)
    if py_cls:
        print(">>> Python class   :", py_cls)
        print(">>> Module         :", py_cls.__module__)
        # File path where this class is defined
        print(">>> Defined at     :", inspect.getfile(py_cls))
    # Field that failed to resolve
    print(">>> Field          :", e.field.name if hasattr(e.field, "name") else e.field)
    raise

# GraphQL Router
graphql_app = GraphQLRouter(
    schema=schema,
    graphiql=False if env == "PROD" else True,  # Enable GraphiQL if set
    context_getter=context_getter,  # Use context_getter to provide context
    subscription_protocols=[GRAPHQL_WS_PROTOCOL, GRAPHQL_TRANSPORT_WS_PROTOCOL],
)
