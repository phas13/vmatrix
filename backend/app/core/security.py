import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload["exp"] = expire
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def create_refresh_token() -> str:
    return str(uuid4())


def hash_token(raw: str) -> str:
    # NEVER store raw refresh tokens; always store the SHA-256 hash
    return hashlib.sha256(raw.encode()).hexdigest()


# /auth/refresh is NOT exempt from CSRF protection — this check is mandatory
def generate_csrf_token() -> str:
    return str(uuid4())


def _get_fernet() -> Fernet:
    key = settings.FERNET_KEY
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt_field(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt_field(token: str) -> str:
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid encrypted value",
        ) from exc
