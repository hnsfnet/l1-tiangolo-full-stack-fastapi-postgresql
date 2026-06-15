import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, delete, func, select

from app import crud
from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models import (
    Item,
    Message,
    UpdatePassword,
    User,
    UserActiveStatusFailure,
    UserActiveStatusResult,
    UserActiveStatusUpdate,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)
from app.utils import generate_new_account_email, send_email

router = APIRouter(prefix="/users", tags=["users"])

# Reasons returned when a deactivation request is rejected by a safety guard.
CANNOT_DEACTIVATE_SELF_DETAIL = "Administrators cannot deactivate their own account"
CANNOT_DEACTIVATE_LAST_SUPERUSER_DETAIL = "Cannot deactivate the last active superuser"


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
)
def read_users(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve users.
    """

    count_statement = select(func.count()).select_from(User)
    count = session.exec(count_statement).one()

    statement = (
        select(User).order_by(col(User.created_at).desc()).offset(skip).limit(limit)
    )
    users = session.exec(statement).all()

    users_public = [UserPublic.model_validate(user) for user in users]
    return UsersPublic(data=users_public, count=count)


@router.post(
    "/", dependencies=[Depends(get_current_active_superuser)], response_model=UserPublic
)
def create_user(*, session: SessionDep, user_in: UserCreate) -> Any:
    """
    Create new user.
    """
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    user = crud.create_user(session=session, user_create=user_in)
    if settings.emails_enabled and user_in.email:
        email_data = generate_new_account_email(
            email_to=user_in.email, username=user_in.email, password=user_in.password
        )
        send_email(
            email_to=user_in.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return user


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """
    Update own user.
    """

    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    user_data = user_in.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@router.patch("/me/password", response_model=Message)
def update_password_me(
    *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """
    Update own password.
    """
    verified, _ = verify_password(body.current_password, current_user.hashed_password)
    if not verified:
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="New password cannot be the same as the current one"
        )
    hashed_password = get_password_hash(body.new_password)
    current_user.hashed_password = hashed_password
    session.add(current_user)
    session.commit()
    return Message(message="Password updated successfully")


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user


@router.delete("/me", response_model=Message)
def delete_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Delete own user.
    """
    if current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    session.delete(current_user)
    session.commit()
    return Message(message="User deleted successfully")


@router.post("/signup", response_model=UserPublic)
def register_user(session: SessionDep, user_in: UserRegister) -> Any:
    """
    Create new user without the need to be logged in.
    """
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )
    user_create = UserCreate.model_validate(user_in)
    user = crud.create_user(session=session, user_create=user_create)
    return user


@router.post(
    "/set-active-status",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserActiveStatusResult,
)
def set_users_active_status(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    body: UserActiveStatusUpdate,
) -> Any:
    """
    Activate or deactivate one or more users in a single request.

    This is the explicit, auditable way to manage account status (rather than
    silently patching the ``is_active`` field). It supports batch operations and
    returns per-user feedback. When deactivating, two safety guards apply:

    * the last remaining active superuser can never be deactivated, so the
      system always keeps at least one active administrator; and
    * an administrator can never deactivate their own account.

    The last-superuser guard is evaluated before the self guard so that a sole
    administrator attempting to disable themselves gets the more informative
    "last active superuser" reason.
    """
    succeeded: list[User] = []
    failed: list[UserActiveStatusFailure] = []

    # Track how many active superusers remain so we never remove the last one.
    active_superuser_count = crud.count_active_superusers(session=session)

    # De-duplicate the requested ids while preserving the original order.
    seen: set[uuid.UUID] = set()
    unique_ids: list[uuid.UUID] = []
    for user_id in body.user_ids:
        if user_id not in seen:
            seen.add(user_id)
            unique_ids.append(user_id)

    for user_id in unique_ids:
        user = session.get(User, user_id)
        if user is None:
            failed.append(
                UserActiveStatusFailure(
                    user_id=user_id, email=None, reason="User not found"
                )
            )
            continue

        if body.is_active:
            # Activating a user is always safe.
            if not user.is_active:
                user.is_active = True
                session.add(user)
            succeeded.append(user)
            continue

        # Deactivation path: apply the safety guards in priority order.
        if user.is_superuser and user.is_active and active_superuser_count <= 1:
            failed.append(
                UserActiveStatusFailure(
                    user_id=user.id,
                    email=user.email,
                    reason=CANNOT_DEACTIVATE_LAST_SUPERUSER_DETAIL,
                )
            )
            continue
        if user.id == current_user.id:
            failed.append(
                UserActiveStatusFailure(
                    user_id=user.id,
                    email=user.email,
                    reason=CANNOT_DEACTIVATE_SELF_DETAIL,
                )
            )
            continue

        if user.is_active:
            user.is_active = False
            session.add(user)
            if user.is_superuser:
                active_superuser_count -= 1
        succeeded.append(user)

    session.commit()
    for user in succeeded:
        session.refresh(user)

    action = "activated" if body.is_active else "deactivated"
    message = f"{len(succeeded)} user(s) {action} successfully"
    if failed:
        message += f", {len(failed)} skipped"

    return UserActiveStatusResult(
        is_active=body.is_active,
        requested_count=len(unique_ids),
        success_count=len(succeeded),
        failure_count=len(failed),
        succeeded=[UserPublic.model_validate(user) for user in succeeded],
        failed=failed,
        message=message,
    )


@router.get("/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    user = session.get(User, user_id)
    if user == current_user:
        return user
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
def update_user(
    *,
    session: SessionDep,
    user_id: uuid.UUID,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """

    db_user = session.get(User, user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )

    db_user = crud.update_user(session=session, db_user=db_user, user_in=user_in)
    return db_user


@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
def delete_user(
    session: SessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> Message:
    """
    Delete a user.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user == current_user:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    statement = delete(Item).where(col(Item.owner_id) == user_id)
    session.exec(statement)
    session.delete(user)
    session.commit()
    return Message(message="User deleted successfully")
