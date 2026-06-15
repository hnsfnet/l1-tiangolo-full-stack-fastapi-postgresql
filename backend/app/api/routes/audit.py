import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import col, func, select

from app.api.deps import SessionDep, get_current_active_superuser
from app.models import AuditLog, AuditLogPublic, AuditLogsPublic

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=AuditLogsPublic,
)
def read_audit_logs(
    session: SessionDep,
    actor_user_id: uuid.UUID | None = None,
    target_type: str | None = None,
    action: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve audit logs. Superuser only.

    Supports filtering by actor, target type, action and a created_at time
    range, ordered from most to least recent.
    """
    filters = []
    if actor_user_id is not None:
        filters.append(AuditLog.actor_user_id == actor_user_id)
    if target_type is not None:
        filters.append(AuditLog.target_type == target_type)
    if action is not None:
        filters.append(AuditLog.action == action)
    if start_time is not None:
        filters.append(AuditLog.created_at >= start_time)
    if end_time is not None:
        filters.append(AuditLog.created_at <= end_time)

    count_statement = select(func.count()).select_from(AuditLog)
    statement = select(AuditLog).order_by(col(AuditLog.created_at).desc())
    for condition in filters:
        count_statement = count_statement.where(condition)
        statement = statement.where(condition)

    count = session.exec(count_statement).one()
    statement = statement.offset(skip).limit(limit)
    logs = session.exec(statement).all()

    data = [AuditLogPublic.model_validate(log) for log in logs]
    return AuditLogsPublic(data=data, count=count)
