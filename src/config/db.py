from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()


# Connect to SQL Server using aioodbc
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "DATABASE_URL",
)

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    # Enable logging if needed
    # echo=True,
    pool_size=200,  # Number of connections stored in the pool
    max_overflow=300,  # Maximum number of additional connections
    future=True,  # Use modern SQLAlchemy API
    pool_recycle=1800,  # Time in seconds before a connection is recycled
)

# Create session factory for AsyncSession
SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Do not expire objects after commit
)

# Dependency to get database session (asynchronous)
async def get_db():
    async with SessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()  # Close session after use
