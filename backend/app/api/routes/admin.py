from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models import Alarm, AuditLog, Document, MachineModel, MaintenanceCase, Message, User
from app.schemas import AuditOut, DashboardOut, UserCreate, UserOut, UserStatusUpdate
from app.services.audit import write_audit
from app.services.graph import graph_service

router = APIRouter(tags=["管理"])


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    since = datetime.now(timezone.utc) - timedelta(days=7)
    return DashboardOut(
        products=db.scalar(select(func.count()).select_from(MachineModel)) or 0,
        published_documents=db.scalar(
            select(func.count()).select_from(Document).where(Document.review_status == "published")
        ) or 0,
        pending_reviews=db.scalar(
            select(func.count()).select_from(Document).where(Document.review_status == "pending")
        ) or 0,
        published_alarms=db.scalar(
            select(func.count()).select_from(Alarm).where(Alarm.review_status == "published")
        ) or 0,
        cases=db.scalar(select(func.count()).select_from(MaintenanceCase)) or 0,
        questions_7d=db.scalar(
            select(func.count()).select_from(Message).where(Message.role == "user", Message.created_at >= since)
        ) or 0,
        graph_coverage=graph_service.coverage_summary(),
    )


@router.get("/admin/users", response_model=list[UserOut])
def users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    return db.scalars(select(User).order_by(User.username)).all()


@router.post("/admin/users", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    if db.scalar(select(User).where(User.username == payload.username)):
        raise HTTPException(status_code=409, detail="用户名已存在")
    user = User(
        username=payload.username,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        role=payload.role,
        active=True,
    )
    db.add(user)
    db.flush()
    write_audit(db, admin, "user.create", "user", user.id, {"role": user.role})
    db.commit()
    db.refresh(user)
    return user


@router.patch("/admin/users/{user_id}/status", response_model=UserOut)
def update_user_status(
    user_id: int,
    payload: UserStatusUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == admin.id and not payload.active:
        raise HTTPException(status_code=409, detail="不能停用当前登录账号")
    if user.role == "admin" and user.active and not payload.active:
        active_admins = db.scalar(
            select(func.count()).select_from(User).where(User.role == "admin", User.active.is_(True))
        ) or 0
        if active_admins <= 1:
            raise HTTPException(status_code=409, detail="必须至少保留一个启用的管理员")
    previous = user.active
    user.active = payload.active
    write_audit(
        db,
        admin,
        "user.enabled" if payload.active else "user.disabled",
        "user",
        user.id,
        {"previous_active": previous, "role": user.role},
    )
    db.commit()
    db.refresh(user)
    return user


@router.post("/admin/users/{user_id}/unlock", response_model=UserOut)
def unlock_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    was_locked = user.locked_until is not None or user.failed_login_count > 0
    user.failed_login_count = 0
    user.locked_until = None
    write_audit(
        db,
        admin,
        "user.unlocked",
        "user",
        user.id,
        {"was_locked": was_locked},
    )
    db.commit()
    db.refresh(user)
    return user


@router.get("/admin/audit", response_model=list[AuditOut])
def audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles("admin", "reviewer")),
):
    return db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()
