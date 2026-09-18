from sqlalchemy.orm import Session

from app.core.request_context import get_request_id
from app.models import AuditLog, User


def write_audit(
    db: Session,
    user: User | None,
    action: str,
    target_type: str,
    target_id: str | int | None = None,
    detail: dict | None = None,
) -> None:
    audit_detail = dict(detail or {})
    request_id = get_request_id()
    if request_id:
        audit_detail.setdefault("request_id", request_id)
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            username=user.username if user else "system",
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            detail=audit_detail,
        )
    )
