import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, or_, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Item,
    ItemCreate,
    ItemDeleteSkip,
    ItemPublic,
    ItemsDelete,
    ItemsDeleteResponse,
    ItemsPublic,
    ItemUpdate,
    Message,
)

router = APIRouter(prefix="/items", tags=["items"])


@router.get("/", response_model=ItemsPublic)
def read_items(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    q: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    owner_id: uuid.UUID | None = None,
) -> Any:
    """
    Retrieve items.

    Supports filtering by a free-text query ``q`` (matched against the title and
    description), by a ``created_at`` range (``created_from`` / ``created_to``)
    and, for superusers only, by ``owner_id``. Non-superusers can only ever see
    their own items, regardless of the ``owner_id`` argument. Results are ordered
    by ``created_at`` descending and ``count`` reflects the applied filters.
    """
    conditions = []

    # Non-superusers are always scoped to their own items; the owner_id filter is
    # only honoured for superusers so a normal user cannot read other people's
    # items by passing it.
    if current_user.is_superuser:
        if owner_id is not None:
            conditions.append(Item.owner_id == owner_id)
    else:
        conditions.append(Item.owner_id == current_user.id)

    if q:
        like = f"%{q}%"
        conditions.append(
            or_(col(Item.title).ilike(like), col(Item.description).ilike(like))
        )
    if created_from is not None:
        conditions.append(col(Item.created_at) >= created_from)
    if created_to is not None:
        conditions.append(col(Item.created_at) <= created_to)

    count_statement = select(func.count()).select_from(Item)
    statement = select(Item)
    if conditions:
        count_statement = count_statement.where(*conditions)
        statement = statement.where(*conditions)

    count = session.exec(count_statement).one()
    statement = statement.order_by(col(Item.created_at).desc()).offset(skip).limit(limit)
    items = session.exec(statement).all()

    items_public = [ItemPublic.model_validate(item) for item in items]
    return ItemsPublic(data=items_public, count=count)


@router.get("/{id}", response_model=ItemPublic)
def read_item(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get item by ID.
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return item


@router.post("/", response_model=ItemPublic)
def create_item(
    *, session: SessionDep, current_user: CurrentUser, item_in: ItemCreate
) -> Any:
    """
    Create new item.
    """
    item = Item.model_validate(item_in, update={"owner_id": current_user.id})
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.put("/{id}", response_model=ItemPublic)
def update_item(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    item_in: ItemUpdate,
) -> Any:
    """
    Update an item.
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    update_dict = item_in.model_dump(exclude_unset=True)
    item.sqlmodel_update(update_dict)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/{id}")
def delete_item(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Delete an item.
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    session.delete(item)
    session.commit()
    return Message(message="Item deleted successfully")


@router.post("/bulk-delete", response_model=ItemsDeleteResponse)
def delete_items(
    session: SessionDep, current_user: CurrentUser, items_in: ItemsDelete
) -> Any:
    """
    Delete multiple items at once.

    Permissions are evaluated per item: a non-superuser can only delete items
    they own. Any id that cannot be deleted (because the item does not exist or
    belongs to another user) is reported in ``skipped`` with a reason rather than
    failing the whole request. Returns how many items were deleted alongside the
    list of skipped ids.
    """
    # Preserve request order while removing duplicate ids.
    unique_ids = list(dict.fromkeys(items_in.ids))

    deleted_count = 0
    skipped: list[ItemDeleteSkip] = []
    for item_id in unique_ids:
        item = session.get(Item, item_id)
        if not item:
            skipped.append(ItemDeleteSkip(id=item_id, reason="Item not found"))
            continue
        if not current_user.is_superuser and item.owner_id != current_user.id:
            skipped.append(
                ItemDeleteSkip(id=item_id, reason="Not enough permissions")
            )
            continue
        session.delete(item)
        deleted_count += 1

    if deleted_count:
        session.commit()

    return ItemsDeleteResponse(
        requested_count=len(unique_ids),
        deleted_count=deleted_count,
        skipped=skipped,
    )
