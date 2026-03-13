"""
P4 JWT 인증 모듈.

사용자 인증, 토큰 발급/검증을 담당한다.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session
import bcrypt

from p4.config import get_config
from p4.db.connection import get_session
from p4.db.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ---------------------------------------------------------------------------
# Pydantic 스키마
# ---------------------------------------------------------------------------

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: str | None = None


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str | None = None
    role: str = "viewer"


class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str | None
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# 헬퍼 함수
# ---------------------------------------------------------------------------

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except ValueError:
        return False


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    config = get_config()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=config.auth.access_token_expire_minutes)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, config.auth.secret_key, algorithm=config.auth.algorithm)


def authenticate_user(username: str, password: str) -> User | None:
    """사용자 인증. 성공 시 User 객체, 실패 시 None."""
    session = get_session()
    try:
        user = session.query(User).filter_by(username=username, is_active=True).first()
        if user and verify_password(password, user.hashed_password):
            return user
        return None
    finally:
        session.close()


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserResponse:
    """JWT 토큰에서 현재 사용자를 추출한다."""
    config = get_config()
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, config.auth.secret_key, algorithms=[config.auth.algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    session = get_session()
    try:
        user = session.query(User).filter_by(username=username, is_active=True).first()
        if user is None:
            raise credentials_exception
        return UserResponse.model_validate(user)
    finally:
        session.close()


def ensure_admin_exists() -> None:
    """기본 admin 계정이 없으면 생성한다."""
    session = get_session()
    try:
        admin = session.query(User).filter_by(username="admin").first()
        if admin is None:
            admin = User(
                username="admin",
                hashed_password=hash_password("admin1234"),
                full_name="Administrator",
                role="admin",
            )
            session.add(admin)
            session.commit()
    finally:
        session.close()
