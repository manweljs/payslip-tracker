import asyncio
import os
from datetime import datetime, timedelta
import secrets
from uuid import UUID
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pytz import utc
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from config.db import get_db
from typing import TYPE_CHECKING, Any, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession


if TYPE_CHECKING:
    from app.account.models import User


SECRET_KEY = os.getenv("SECRET_KEY", "secret")

ACCESS_TOKEN_EXPIRE_DAY = 1
ALGORITHM = "HS256"


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/Account/Token")


role_cache: Dict[str, str] = {}
cache_lock = asyncio.Lock()  # Lock to avoid race conditions in async environment


async def create_access_token(
    user: "User",
    role: Optional[str] = None,
    account_id: Optional[UUID] = None,
    days: Optional[int] = ACCESS_TOKEN_EXPIRE_DAY,
):
    """
    Create a JWT access token with expiration time based on the given number of days.

    Parameters:
        user (User): User object to be included in the token.
        role (Optional[str]): User role to be included in the token. Default is None.
        days (Optional[int]): Number of days before the token expires. Default is 1 day.

    Returns:
        tuple: Encrypted JWT token and expiration time (in seconds).
    """

    expire = datetime.now(utc) + timedelta(days=days)

    # Calculate expires_in directly from the number of days
    expires_in = days * 24 * 60 * 60  # Number of seconds in several days

    # Prepare payload for JWT token
    to_encode = {
        "sub": str(user.id),
        "role": str(role),
        "account_id": str(account_id) if account_id else None,
        "exp": expire,
    }

    # Encode JWT token
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    # Return JWT token and expires_in
    return encoded_jwt, expires_in


async def create_refresh_token(user: "User"):

    # Refresh token is valid for 30 days
    expire = datetime.now(utc) + timedelta(days=30)
    to_encode = {"sub": str(user.id), "exp": expire}
    refresh_token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return refresh_token


async def validate_refresh_token(refresh_token: str):
    try:
        from app.account.models import User

        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=ALGORITHM)
        user_id: str = payload.get("sub", None)
        user = await User.get(id=user_id)
        if not user:
            raise HTTPException(status_code=401, detail=f"Invalid token")
        access_token = await create_access_token(user)
        return access_token
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


# get_current_user function that uses cache to store role
async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
):

    try:
        from app.account.models import User

        # Decode token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub", None)

        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")


        # If not in cache, get from database
        user = await User.get(db, id=user_id, relations=False)
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        # Get role from token
        role = payload.get("role", None)
        if role is None:
            raise HTTPException(status_code=401, detail="Role not found in token")

    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Unexpected error: {e}")

    return user


async def get_current_user_ws(token: str) -> "User":
    from app.account.models import User

    async for db in get_db():
        credentials_exception = HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id is None:
                raise credentials_exception
        except Exception as e:
            raise credentials_exception

        user = await User.get(db, id=user_id)
        if user is None:
            raise credentials_exception
        return user


async def get_app(token):
    print(token)
    return True


async def create_temporary_token(
    user: "User",
    expire_minutes: int = 1,
    payload: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a temporary JWT token for user.
    Default expire time is 1 minute.
    """
    try:
        if not user:
            raise ValueError("User is required to create temporary token")
        expire = datetime.now() + timedelta(minutes=expire_minutes)
        payload = {
            "sub": str(user.id),  # Main information in the token
            "exp": expire,        # Expiration time
            **(payload or {}),
        }

        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        return token
    except Exception as e:
        err = f"Error creating temporary token: {str(e)}"
        raise HTTPException(status_code=500, detail=err)


async def validate_token(
    token: str,
    allow_expired: bool = False,
) -> Dict[str, Any]:
    """
    Validate JWT token.

    Args:
      token: JWT string.
      allow_expired: if True, payload is still returned even if token is expired.

    Returns:
      payload (claim) as dict.

    Raises:
      HTTPException 401 if token is invalid or expired (if allow_expired=False),
      HTTPException 500 for unexpected errors.
    """
    try:
        if allow_expired:
            # Ignore exp validation, but still verify signature
            payload = jwt.decode(
                token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False}
            )
        else:
            # Default: verify all (including exp)
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload

    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid token") from e

    except HTTPException as http_err:
        # let other HTTPExceptions pass through
        raise http_err

    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Unexpected error occurred"
        ) from e

