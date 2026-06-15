import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import Item, ItemCreate
from tests.utils.item import create_random_item
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string


def test_create_item(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"title": "Foo", "description": "Fighters"}
    response = client.post(
        f"{settings.API_V1_STR}/items/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == data["title"]
    assert content["description"] == data["description"]
    assert "id" in content
    assert "owner_id" in content


def test_read_item(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    item = create_random_item(db)
    response = client.get(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == item.title
    assert content["description"] == item.description
    assert content["id"] == str(item.id)
    assert content["owner_id"] == str(item.owner_id)


def test_read_item_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/items/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Item not found"


def test_read_item_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    item = create_random_item(db)
    response = client.get(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "Not enough permissions"


def test_read_items(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    create_random_item(db)
    create_random_item(db)
    response = client.get(
        f"{settings.API_V1_STR}/items/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert len(content["data"]) >= 2


def test_update_item(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    item = create_random_item(db)
    data = {"title": "Updated title", "description": "Updated description"}
    response = client.put(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == data["title"]
    assert content["description"] == data["description"]
    assert content["id"] == str(item.id)
    assert content["owner_id"] == str(item.owner_id)


def test_update_item_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"title": "Updated title", "description": "Updated description"}
    response = client.put(
        f"{settings.API_V1_STR}/items/{uuid.uuid4()}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Item not found"


def test_update_item_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    item = create_random_item(db)
    data = {"title": "Updated title", "description": "Updated description"}
    response = client.put(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=normal_user_token_headers,
        json=data,
    )
    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "Not enough permissions"


def test_delete_item(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    item = create_random_item(db)
    response = client.delete(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["message"] == "Item deleted successfully"


def test_delete_item_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/items/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Item not found"


def test_delete_item_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    item = create_random_item(db)
    response = client.delete(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "Not enough permissions"


def _make_item(
    db: Session,
    owner_id: uuid.UUID,
    title: str | None = None,
    description: str | None = None,
) -> Item:
    item_in = ItemCreate(
        title=title if title is not None else random_lower_string(),
        description=description,
    )
    return crud.create_item(session=db, item_in=item_in, owner_id=owner_id)


def test_read_items_filter_by_q(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    token = random_lower_string()
    user = create_random_user(db)
    # Two matches via title, one match via description, plus unrelated noise.
    _make_item(db, user.id, title=f"{token} title", description="desc")
    _make_item(db, user.id, title=f"another {token}", description="desc")
    _make_item(db, user.id, title="plain", description=f"contains {token} here")
    _make_item(db, user.id, title="unrelated", description="nothing relevant")

    response = client.get(
        f"{settings.API_V1_STR}/items/",
        headers=superuser_token_headers,
        params={"q": token},
    )
    assert response.status_code == 200
    content = response.json()
    # count must be based on the filter, not the whole table.
    assert content["count"] == 3
    assert len(content["data"]) == 3
    for item in content["data"]:
        assert token in item["title"] or token in (item["description"] or "")


def test_read_items_filter_by_owner_id_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    token = random_lower_string()
    owner = create_random_user(db)
    other = create_random_user(db)
    _make_item(db, owner.id, title=f"{token} a")
    _make_item(db, owner.id, title=f"{token} b")
    _make_item(db, other.id, title=f"{token} c")

    response = client.get(
        f"{settings.API_V1_STR}/items/",
        headers=superuser_token_headers,
        params={"q": token, "owner_id": str(owner.id)},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["count"] == 2
    assert len(content["data"]) == 2
    assert all(item["owner_id"] == str(owner.id) for item in content["data"])


def test_read_items_owner_id_ignored_for_normal_user(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    token = random_lower_string()
    normal_user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
    assert normal_user is not None
    other = create_random_user(db)
    _make_item(db, normal_user.id, title=f"{token} mine")
    _make_item(db, other.id, title=f"{token} theirs")

    # A normal user tries to scope the query to another owner's items.
    response = client.get(
        f"{settings.API_V1_STR}/items/",
        headers=normal_user_token_headers,
        params={"q": token, "owner_id": str(other.id)},
    )
    assert response.status_code == 200
    content = response.json()
    # The owner_id filter must be ignored: only the user's own item is returned.
    assert content["count"] == 1
    assert all(item["owner_id"] == str(normal_user.id) for item in content["data"])


def test_read_items_filter_by_created_range(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    token = random_lower_string()
    user = create_random_user(db)
    _make_item(db, user.id, title=f"{token} x")
    _make_item(db, user.id, title=f"{token} y")

    base = f"{settings.API_V1_STR}/items/"

    # A wide range that includes "now" returns everything matching the query.
    response_in = client.get(
        base,
        headers=superuser_token_headers,
        params={
            "q": token,
            "created_from": "2000-01-01T00:00:00",
            "created_to": "2999-01-01T00:00:00",
        },
    )
    assert response_in.status_code == 200
    assert response_in.json()["count"] == 2

    # created_to far in the past excludes everything.
    response_past = client.get(
        base,
        headers=superuser_token_headers,
        params={"q": token, "created_to": "2000-01-01T00:00:00"},
    )
    assert response_past.status_code == 200
    assert response_past.json()["count"] == 0

    # created_from far in the future excludes everything.
    response_future = client.get(
        base,
        headers=superuser_token_headers,
        params={"q": token, "created_from": "2999-01-01T00:00:00"},
    )
    assert response_future.status_code == 200
    assert response_future.json()["count"] == 0


def test_read_items_ordered_by_created_at_desc(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    token = random_lower_string()
    user = create_random_user(db)
    _make_item(db, user.id, title=f"{token} first")
    _make_item(db, user.id, title=f"{token} second")
    _make_item(db, user.id, title=f"{token} third")

    response = client.get(
        f"{settings.API_V1_STR}/items/",
        headers=superuser_token_headers,
        params={"q": token},
    )
    assert response.status_code == 200
    created_values = [item["created_at"] for item in response.json()["data"]]
    assert created_values == sorted(created_values, reverse=True)


def test_bulk_delete_items_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    user = create_random_user(db)
    ids = [str(_make_item(db, user.id).id) for _ in range(3)]

    response = client.post(
        f"{settings.API_V1_STR}/items/bulk-delete",
        headers=superuser_token_headers,
        json={"ids": ids},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["requested_count"] == 3
    assert content["deleted_count"] == 3
    assert content["skipped"] == []

    for item_id in ids:
        check = client.get(
            f"{settings.API_V1_STR}/items/{item_id}",
            headers=superuser_token_headers,
        )
        assert check.status_code == 404


def test_bulk_delete_items_partial_missing(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    user = create_random_user(db)
    existing = str(_make_item(db, user.id).id)
    missing = str(uuid.uuid4())

    response = client.post(
        f"{settings.API_V1_STR}/items/bulk-delete",
        headers=superuser_token_headers,
        json={"ids": [existing, missing]},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["requested_count"] == 2
    assert content["deleted_count"] == 1
    assert len(content["skipped"]) == 1
    assert content["skipped"][0]["id"] == missing
    assert content["skipped"][0]["reason"] == "Item not found"


def test_bulk_delete_items_normal_user_cannot_delete_others(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    other = create_random_user(db)
    item = _make_item(db, other.id)

    response = client.post(
        f"{settings.API_V1_STR}/items/bulk-delete",
        headers=normal_user_token_headers,
        json={"ids": [str(item.id)]},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["requested_count"] == 1
    assert content["deleted_count"] == 0
    assert len(content["skipped"]) == 1
    assert content["skipped"][0]["id"] == str(item.id)
    assert content["skipped"][0]["reason"] == "Not enough permissions"

    # The foreign item must still exist.
    check = client.get(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=superuser_token_headers,
    )
    assert check.status_code == 200


def test_bulk_delete_items_mixed_permissions(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    normal_user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
    assert normal_user is not None
    other = create_random_user(db)
    own = _make_item(db, normal_user.id)
    foreign = _make_item(db, other.id)

    response = client.post(
        f"{settings.API_V1_STR}/items/bulk-delete",
        headers=normal_user_token_headers,
        json={"ids": [str(own.id), str(foreign.id)]},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["deleted_count"] == 1
    assert len(content["skipped"]) == 1
    assert content["skipped"][0]["id"] == str(foreign.id)
    assert content["skipped"][0]["reason"] == "Not enough permissions"

    # The user's own item is gone, the foreign one remains.
    own_check = client.get(
        f"{settings.API_V1_STR}/items/{own.id}",
        headers=superuser_token_headers,
    )
    assert own_check.status_code == 404
    foreign_check = client.get(
        f"{settings.API_V1_STR}/items/{foreign.id}",
        headers=superuser_token_headers,
    )
    assert foreign_check.status_code == 200


def test_bulk_delete_items_deduplicates_ids(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    user = create_random_user(db)
    item_id = str(_make_item(db, user.id).id)

    response = client.post(
        f"{settings.API_V1_STR}/items/bulk-delete",
        headers=superuser_token_headers,
        json={"ids": [item_id, item_id]},
    )
    assert response.status_code == 200
    content = response.json()
    # Duplicates collapse to a single delete, not a delete + "not found".
    assert content["requested_count"] == 1
    assert content["deleted_count"] == 1
    assert content["skipped"] == []


def test_bulk_delete_items_empty_payload(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/items/bulk-delete",
        headers=superuser_token_headers,
        json={"ids": []},
    )
    assert response.status_code == 422
