from fastapi import APIRouter

router = APIRouter(prefix="/api/Tracker", tags=["Tracker"])

@router.get("/")
async def read_root():
    return {"message": "Welcome to the Payslip Tracker API!"}

