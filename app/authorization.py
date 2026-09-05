from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.auth import get_current_user
from app.enums import UserRole
from app.models import User


def require_roles(*allowed_roles: UserRole) -> Callable[[User], User]:
    def role_dependency(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

        return current_user

    return role_dependency
