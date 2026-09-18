from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.core.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import LoginRequest, PasswordChangeRequest, TokenResponse, UserOut
from app.services.audit import write_audit

router = APIRouter(prefix="/auth", tags=["认证"])
DUMMY_PASSWORD_HASH = hash_password("not-a-real-account-password", salt="00" * 16)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    settings = get_settings()
    now = datetime.now(timezone.utc)
    user = db.scalar(
        select(User).where(User.username == payload.username).with_for_update()
    )

    if user and user.locked_until:
        locked_until = _utc(user.locked_until)
        if locked_until > now:
            retry_after = max(1, int((locked_until - now).total_seconds()))
            write_audit(
                db,
                user,
                "auth.login_blocked",
                "user",
                user.id,
                {"retry_after_seconds": retry_after},
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="登录尝试过多，请稍后重试",
                headers={"Retry-After": str(retry_after)},
            )
        user.failed_login_count = 0
        user.locked_until = None

    password_hash = user.password_hash if user else DUMMY_PASSWORD_HASH
    password_valid = verify_password(payload.password, password_hash)
    if not user or not user.active or not password_valid:
        locked = False
        attempts = 0
        if user and user.active:
            user.failed_login_count += 1
            attempts = user.failed_login_count
            if attempts >= settings.login_max_failures:
                user.locked_until = now + timedelta(minutes=settings.login_lock_minutes)
                locked = True
        write_audit(
            db,
            user,
            "auth.login_failed",
            "user",
            user.id if user else None,
            detail={
                "username": payload.username,
                "failed_attempts": attempts,
                "account_locked": locked,
            },
        )
        db.commit()
        if locked:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="登录尝试过多，请稍后重试",
                headers={"Retry-After": str(settings.login_lock_minutes * 60)},
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    token = create_access_token(user.username, user.role, user.password_hash)
    write_audit(db, user, "auth.login", "user", user.id)
    db.commit()
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password")
def change_password(
    payload: PasswordChangeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")
    user.password_hash = hash_password(payload.new_password)
    write_audit(db, user, "auth.password_changed", "user", user.id)
    db.commit()
    return {"status": "changed"}
