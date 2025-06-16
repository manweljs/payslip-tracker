from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware
from routes import router
app = FastAPI(
    title="Payslip Tracker API",
    description="API for Payslip Tracker",
    version="0.1.0",
    docs_url="/"
)


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router=router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)


