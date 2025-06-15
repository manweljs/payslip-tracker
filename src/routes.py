from fastapi import APIRouter
router = APIRouter()

from app.tracker.routers import router as tracker_router
from base.gql.app import graphql_app

router.include_router(tracker_router)
router.include_router(graphql_app, prefix="/graphql")