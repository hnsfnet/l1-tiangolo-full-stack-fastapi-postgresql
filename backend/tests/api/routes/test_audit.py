import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from app import crud
from app.core.config import settings
from app.models import AuditAction, AuditLog, AuditTargetType, Item
from tests.utils.utils import random_email, random_lower_string


def _read_logs(
    client: TestClient, headers: dict[str, str], **params: object
) -> dict:
    r = client.get(
        f"{settings.API_V1_STR}/audit/",
        headers=headers,
        params={k: v for k, v in params.items() if v is not None},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _me_id(client: TestClient, headers: dict[str, str]) -> str:
    r = client.get(f"{settings.API_V1_STR}/users/me", headers=headers)
    return r.json()["id"]


def _create_user(
    client: TestClient,
    headers: dict[str, str],
    email: str | None = None,
) -> object:
    return client.post(
        f"{settings.API_V1_STR}/users/",
        headers=headers,
        json={
            "email": email or random_email(),
            "password": random_lower_string(),
        },
    )


def _create_item(client: TestClient, headers: dict[str, str], title: str) -> object:
    return client.post(
        f"{settings.API_V1_STR}/items/",
        headers=headers,
        json={"title": title, "description": "audit test"},
    )


# --- Permission control -----------------------------------------------------


def test_read_audit_logs_normal_user_forbidden(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/audit/", headers=normal_user_token_headers
    )
    assert r.status_code == 403


def test_read_audit_logs_requires_auth(client: TestClient) -> None:
    r = client.get(f"{settings.API_V1_STR}/audit/")
    assert r.status_code == 401


def test_read_audit_logs_superuser_ok(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    logs = _read_logs(client, superuser_token_headers)
    assert "data" in logs
    assert "count" in logs


# --- Logging of successful operations ---------------------------------------


def test_create_user_writes_audit_log(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    actor_id = _me_id(client, superuser_token_headers)
    email = random_email()
    r = _create_user(client, superuser_token_headers, email=email)
    assert 200 <= r.status_code < 300
    user_id = r.json()["id"]

    logs = _read_logs(
        client,
        superuser_token_headers,
        action=AuditAction.USER_CREATE,
        target_type=AuditTargetType.USER,
    )
    matches = [log for log in logs["data"] if log["target_id"] == user_id]
    assert len(matches) == 1
    log = matches[0]
    assert log["actor_user_id"] == actor_id
    assert log["target_type"] == AuditTargetType.USER
    assert email in log["summary"]


def test_create_item_writes_audit_log(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
) -> None:
    actor_id = _me_id(client, normal_user_token_headers)
    r = _create_item(client, normal_user_token_headers, "audit create item")
    assert 200 <= r.status_code < 300
    item_id = r.json()["id"]

    logs = _read_logs(
        client,
        superuser_token_headers,
        action=AuditAction.ITEM_CREATE,
        target_type=AuditTargetType.ITEM,
    )
    matches = [log for log in logs["data"] if log["target_id"] == item_id]
    assert len(matches) == 1
    assert matches[0]["actor_user_id"] == actor_id


def test_update_item_writes_audit_log(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
) -> None:
    r = _create_item(client, normal_user_token_headers, "before update")
    item_id = r.json()["id"]
    r = client.put(
        f"{settings.API_V1_STR}/items/{item_id}",
        headers=normal_user_token_headers,
        json={"title": "after update"},
    )
    assert 200 <= r.status_code < 300

    logs = _read_logs(
        client, superuser_token_headers, action=AuditAction.ITEM_UPDATE
    )
    assert any(log["target_id"] == item_id for log in logs["data"])


def test_delete_item_writes_audit_log(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
) -> None:
    r = _create_item(client, normal_user_token_headers, "to delete")
    item_id = r.json()["id"]
    r = client.delete(
        f"{settings.API_V1_STR}/items/{item_id}",
        headers=normal_user_token_headers,
    )
    assert 200 <= r.status_code < 300

    logs = _read_logs(
        client, superuser_token_headers, action=AuditAction.ITEM_DELETE
    )
    assert any(log["target_id"] == item_id for log in logs["data"])


def test_delete_user_writes_audit_log(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = _create_user(client, superuser_token_headers)
    user_id = r.json()["id"]
    r = client.delete(
        f"{settings.API_V1_STR}/users/{user_id}", headers=superuser_token_headers
    )
    assert 200 <= r.status_code < 300

    logs = _read_logs(
        client, superuser_token_headers, action=AuditAction.USER_DELETE
    )
    assert any(log["target_id"] == user_id for log in logs["data"])


def test_update_user_logs_update_and_activation_toggle(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = _create_user(client, superuser_token_headers)
    user_id = r.json()["id"]

    # A regular field change is recorded as a plain update.
    r = client.patch(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=superuser_token_headers,
        json={"full_name": "Renamed"},
    )
    assert 200 <= r.status_code < 300
    logs = _read_logs(
        client, superuser_token_headers, action=AuditAction.USER_UPDATE
    )
    assert any(log["target_id"] == user_id for log in logs["data"])

    # Disabling the user is recorded as an explicit deactivate action.
    r = client.patch(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=superuser_token_headers,
        json={"is_active": False},
    )
    assert 200 <= r.status_code < 300
    logs = _read_logs(
        client, superuser_token_headers, action=AuditAction.USER_DEACTIVATE
    )
    assert any(log["target_id"] == user_id for log in logs["data"])

    # Re-enabling is recorded as an explicit activate action.
    r = client.patch(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=superuser_token_headers,
        json={"is_active": True},
    )
    assert 200 <= r.status_code < 300
    logs = _read_logs(
        client, superuser_token_headers, action=AuditAction.USER_ACTIVATE
    )
    assert any(log["target_id"] == user_id for log in logs["data"])


# --- Filtering --------------------------------------------------------------


def test_audit_filter_by_actor(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
) -> None:
    superuser_id = _me_id(client, superuser_token_headers)
    normal_id = _me_id(client, normal_user_token_headers)

    r = _create_item(client, normal_user_token_headers, "actor filter item")
    item_id = r.json()["id"]

    # Filtering by the normal user returns this item and only their entries.
    logs = _read_logs(
        client,
        superuser_token_headers,
        actor_user_id=normal_id,
        target_type=AuditTargetType.ITEM,
    )
    assert any(log["target_id"] == item_id for log in logs["data"])
    assert all(log["actor_user_id"] == normal_id for log in logs["data"])

    # Filtering by a different actor must not return it.
    logs = _read_logs(
        client,
        superuser_token_headers,
        actor_user_id=superuser_id,
        target_type=AuditTargetType.ITEM,
    )
    assert all(log["target_id"] != item_id for log in logs["data"])


def test_audit_filter_by_action_and_target_type(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = _create_user(client, superuser_token_headers)
    user_id = r.json()["id"]

    logs = _read_logs(
        client,
        superuser_token_headers,
        action=AuditAction.USER_CREATE,
        target_type=AuditTargetType.USER,
    )
    assert any(log["target_id"] == user_id for log in logs["data"])
    assert all(log["action"] == AuditAction.USER_CREATE for log in logs["data"])
    assert all(
        log["target_type"] == AuditTargetType.USER for log in logs["data"]
    )


def test_audit_filter_by_time_range(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    before = datetime.now(timezone.utc) - timedelta(seconds=2)
    r = _create_user(client, superuser_token_headers)
    user_id = r.json()["id"]

    # start_time at/just before creation includes the new entry.
    logs = _read_logs(
        client,
        superuser_token_headers,
        action=AuditAction.USER_CREATE,
        start_time=before.isoformat(),
    )
    assert any(log["target_id"] == user_id for log in logs["data"])

    # end_time before creation excludes the new entry.
    logs = _read_logs(
        client,
        superuser_token_headers,
        action=AuditAction.USER_CREATE,
        end_time=before.isoformat(),
    )
    assert all(log["target_id"] != user_id for log in logs["data"])


def test_audit_pagination(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    # Generate a few entries so there is something to page through.
    for _ in range(3):
        _create_user(client, superuser_token_headers)

    page = _read_logs(client, superuser_token_headers, skip=0, limit=2)
    assert len(page["data"]) <= 2
    assert page["count"] >= 3


# --- Consistency: failures and rejected requests must not be logged ---------


def test_rejected_request_is_not_logged(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    email = random_email()
    r = _create_user(client, superuser_token_headers, email=email)
    assert 200 <= r.status_code < 300

    before = _read_logs(
        client, superuser_token_headers, action=AuditAction.USER_CREATE
    )["count"]

    # Duplicate email is rejected with 400 and must not produce a log entry.
    r = _create_user(client, superuser_token_headers, email=email)
    assert r.status_code == 400

    after = _read_logs(
        client, superuser_token_headers, action=AuditAction.USER_CREATE
    )["count"]
    assert after == before


def test_failed_transaction_does_not_persist_audit_log(db: Session) -> None:
    """A rolled-back transaction must not leave an audit log behind.

    The audit log is staged in the same transaction as the business operation,
    so when the commit fails (here a foreign-key violation) both are discarded.
    """
    before = db.exec(select(func.count()).select_from(AuditLog)).one()

    # Stage an item referencing a non-existent owner (fails the FK on commit)
    # together with an audit log entry, mirroring a route's unit of work.
    bad_item = Item(title="invalid", owner_id=uuid.uuid4())
    db.add(bad_item)
    crud.create_audit_log(
        session=db,
        actor_user_id=None,
        action=AuditAction.ITEM_CREATE,
        target_type=AuditTargetType.ITEM,
        target_id=str(bad_item.id),
        summary="should never be persisted",
    )

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    after = db.exec(select(func.count()).select_from(AuditLog)).one()
    assert after == before
