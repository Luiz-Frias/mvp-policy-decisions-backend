# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.
# SPDX-License-Identifier: AGPL-3.0-or-later AND LicenseRef-PolicyCore-Commercial
"""WebSocket room permissions and access control system."""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field, validator

from pd_prime_demo.core.result_types import Err, Ok, Result
from pd_prime_demo.models.base import BaseModelConfig

# Auto-generated models


@beartype
class MetadataData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


logger = logging.getLogger(__name__)


class PermissionType(str, Enum):
    """Types of permissions."""

    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    MODERATE = "moderate"
    INVITE = "invite"
    DELETE = "delete"


class RoomType(str, Enum):
    """Types of rooms."""

    QUOTE = "quote"
    POLICY = "policy"
    ADMIN = "admin"
    ANALYTICS = "analytics"
    NOTIFICATION = "notification"
    CUSTOMER = "customer"
    AGENT = "agent"
    BROADCAST = "broadcast"


class UserRole(str, Enum):
    """User roles for permission checking."""

    GUEST = "guest"
    CUSTOMER = "customer"
    AGENT = "agent"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"
    SYSTEM = "system"


class RoomPermission(BaseModel):
    """A permission for a room."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    room_id: str = Field(..., min_length=1, max_length=200)
    user_id: UUID = Field(...)
    permission_type: PermissionType = Field(...)
    granted_by: UUID = Field(...)
    granted_at: datetime = Field(default_factory=datetime.now)
    expires_at: datetime | None = Field(default=None)
    metadata: MetadataData = Field(default_factory=dict)

    @beartype
    def is_expired(self) -> bool:
        """Check if permission has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    @beartype
    def is_valid(self) -> bool:
        """Check if permission is valid (not expired)."""
        return not self.is_expired()


class RoomAccessRule(BaseModel):
    """Rule for room access control."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    room_type: RoomType = Field(...)
    required_role: UserRole = Field(...)
    required_permissions: list[PermissionType] = Field(default_factory=list)
    allow_owner_access: bool = Field(default=True)
    allow_public_read: bool = Field(default=False)
    max_participants: int | None = Field(default=None, ge=1)

    @validator("required_permissions")
    @classmethod
    @beartype
    def validate_permissions(cls, v: list[PermissionType]) -> list[PermissionType]:
        """Validate that permissions are unique."""
        if len(v) != len(set(v)):
            raise ValueError("Permissions must be unique")
        return v


class UserPermissions(BaseModel):
    """User's permissions and roles."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    user_id: UUID = Field(...)
    role: UserRole = Field(...)
    permissions: set[str] = Field(default_factory=set)
    room_permissions: dict[str, list[PermissionType]] = Field(default_factory=dict)
    is_active: bool = Field(default=True)
    last_activity: datetime = Field(default_factory=datetime.now)

    @beartype
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        return permission in self.permissions

    @beartype
    def has_room_permission(self, room_id: str, permission: PermissionType) -> bool:
        """Check if user has a specific room permission."""
        return (
            room_id in self.room_permissions
            and permission in self.room_permissions[room_id]
        )

    @beartype
    def can_access_room(self, room_id: str) -> bool:
        """Check if user can access a room (has any permission)."""
        return (
            room_id in self.room_permissions and len(self.room_permissions[room_id]) > 0
        )


class RoomPermissionManager:
    """Manages room permissions and access control."""

    def __init__(self) -> None:
        """Initialize permission manager."""
        # Permission storage
        self._user_permissions: dict[UUID, UserPermissions] = {}
        self._room_permissions: dict[str, list[RoomPermission]] = {}

        # Access rules by room type
        self._access_rules: dict[RoomType, RoomAccessRule] = (
            self._create_default_rules()
        )

        # Room ownership tracking
        self._room_owners: dict[str, UUID] = {}

        # Room participant counts
        self._room_participants: dict[str, set[UUID]] = {}

        # Permission cache for performance
        self._permission_cache: dict[str, dict[str, Any]] = {}
        self._cache_ttl = 300  # 5 minutes

    def _create_default_rules(self) -> dict[RoomType, RoomAccessRule]:
        """Create default access rules for different room types."""
        return {
            RoomType.QUOTE: RoomAccessRule(
                room_type=RoomType.QUOTE,
                required_role=UserRole.CUSTOMER,
                required_permissions=[PermissionType.READ],
                allow_owner_access=True,
                allow_public_read=False,
                max_participants=10,
            ),
            RoomType.POLICY: RoomAccessRule(
                room_type=RoomType.POLICY,
                required_role=UserRole.CUSTOMER,
                required_permissions=[PermissionType.READ],
                allow_owner_access=True,
                allow_public_read=False,
                max_participants=10,
            ),
            RoomType.ADMIN: RoomAccessRule(
                room_type=RoomType.ADMIN,
                required_role=UserRole.ADMIN,
                required_permissions=[PermissionType.READ, PermissionType.ADMIN],
                allow_owner_access=False,
                allow_public_read=False,
                max_participants=5,
            ),
            RoomType.ANALYTICS: RoomAccessRule(
                room_type=RoomType.ANALYTICS,
                required_role=UserRole.AGENT,
                required_permissions=[PermissionType.READ],
                allow_owner_access=False,
                allow_public_read=False,
                max_participants=20,
            ),
            RoomType.NOTIFICATION: RoomAccessRule(
                room_type=RoomType.NOTIFICATION,
                required_role=UserRole.CUSTOMER,
                required_permissions=[PermissionType.READ],
                allow_owner_access=True,
                allow_public_read=False,
                max_participants=1,
            ),
            RoomType.CUSTOMER: RoomAccessRule(
                room_type=RoomType.CUSTOMER,
                required_role=UserRole.CUSTOMER,
                required_permissions=[PermissionType.READ, PermissionType.WRITE],
                allow_owner_access=True,
                allow_public_read=False,
                max_participants=5,
            ),
            RoomType.AGENT: RoomAccessRule(
                room_type=RoomType.AGENT,
                required_role=UserRole.AGENT,
                required_permissions=[PermissionType.READ, PermissionType.WRITE],
                allow_owner_access=False,
                allow_public_read=False,
                max_participants=50,
            ),
            RoomType.BROADCAST: RoomAccessRule(
                room_type=RoomType.BROADCAST,
                required_role=UserRole.GUEST,
                required_permissions=[PermissionType.READ],
                allow_owner_access=False,
                allow_public_read=True,
                max_participants=None,  # Unlimited
            ),
        }

    @beartype
    def set_user_permissions(self, user_permissions: UserPermissions) -> None:
        """Set permissions for a user."""
        self._user_permissions[user_permissions.user_id] = user_permissions
        self._clear_user_cache(user_permissions.user_id)

    @beartype
    def get_user_permissions(self, user_id: UUID) -> UserPermissions | None:
        """Get permissions for a user."""
        return self._user_permissions.get(user_id)

    @beartype
    def grant_room_permission(
        self,
        room_id: str,
        user_id: UUID,
        permission_type: PermissionType,
        granted_by: UUID,
        expires_at: datetime | None = None,
    ) -> Result[None, str]:
        """Grant a room permission to a user."""
        try:
            # Check if granter has permission to grant
            if not self.can_user_perform_action(
                granted_by, room_id, PermissionType.ADMIN
            ):
                return Err(
                    f"User {granted_by} does not have permission to grant permissions in room {room_id}"
                )

            # Create permission
            permission = RoomPermission(
                room_id=room_id,
                user_id=user_id,
                permission_type=permission_type,
                granted_by=granted_by,
                expires_at=expires_at,
            )

            # Add to room permissions
            if room_id not in self._room_permissions:
                self._room_permissions[room_id] = []

            # Remove existing permission of same type
            self._room_permissions[room_id] = [
                p
                for p in self._room_permissions[room_id]
                if not (p.user_id == user_id and p.permission_type == permission_type)
            ]

            # Add new permission
            self._room_permissions[room_id].append(permission)

            # Update user permissions
            user_perms = self._user_permissions.get(user_id)
            if user_perms:
                room_perms = user_perms.room_permissions.get(room_id, [])
                if permission_type not in room_perms:
                    room_perms.append(permission_type)

                    updated_room_perms = user_perms.room_permissions.copy()
                    updated_room_perms[room_id] = room_perms

                    self._user_permissions[user_id] = user_perms.model_copy(
                        update={"room_permissions": updated_room_perms}
                    )

            self._clear_user_cache(user_id)

            logger.info(
                f"Granted {permission_type} permission to user {user_id} in room {room_id}"
            )
            return Ok(None)

        except Exception as e:
            logger.error(f"Failed to grant permission: {e}")
            return Err(f"Failed to grant permission: {str(e)}")

    @beartype
    def revoke_room_permission(
        self,
        room_id: str,
        user_id: UUID,
        permission_type: PermissionType,
        revoked_by: UUID,
    ) -> Result[None, str]:
        """Revoke a room permission from a user."""
        try:
            # Check if revoker has permission to revoke
            if not self.can_user_perform_action(
                revoked_by, room_id, PermissionType.ADMIN
            ):
                return Err(
                    f"User {revoked_by} does not have permission to revoke permissions in room {room_id}"
                )

            # Remove from room permissions
            if room_id in self._room_permissions:
                self._room_permissions[room_id] = [
                    p
                    for p in self._room_permissions[room_id]
                    if not (
                        p.user_id == user_id and p.permission_type == permission_type
                    )
                ]

            # Update user permissions
            user_perms = self._user_permissions.get(user_id)
            if user_perms and room_id in user_perms.room_permissions:
                room_perms = [
                    p
                    for p in user_perms.room_permissions[room_id]
                    if p != permission_type
                ]

                updated_room_perms = user_perms.room_permissions.copy()
                if room_perms:
                    updated_room_perms[room_id] = room_perms
                else:
                    del updated_room_perms[room_id]

                self._user_permissions[user_id] = user_perms.model_copy(
                    update={"room_permissions": updated_room_perms}
                )

            self._clear_user_cache(user_id)

            logger.info(
                f"Revoked {permission_type} permission from user {user_id} in room {room_id}"
            )
            return Ok(None)

        except Exception as e:
            logger.error(f"Failed to revoke permission: {e}")
            return Err(f"Failed to revoke permission: {str(e)}")

    @beartype
    def set_room_owner(self, room_id: str, owner_id: UUID) -> None:
        """Set the owner of a room."""
        self._room_owners[room_id] = owner_id
        self._clear_room_cache(room_id)

    @beartype
    def get_room_owner(self, room_id: str) -> UUID | None:
        """Get the owner of a room."""
        return self._room_owners.get(room_id)

    @beartype
    def can_user_access_room(self, user_id: UUID, room_id: str) -> bool:
        """Check if a user can access a room."""
        # Check cache first
        cache_key = f"access:{user_id}:{room_id}"
        cached = self._get_cached_result(cache_key)
        if cached is not None:
            return cached

        result = self._check_room_access(user_id, room_id)
        self._cache_result(cache_key, result)
        return result

    @beartype
    def can_user_perform_action(
        self, user_id: UUID, room_id: str, action: PermissionType
    ) -> bool:
        """Check if a user can perform a specific action in a room."""
        # Check cache first
        cache_key = f"action:{user_id}:{room_id}:{action}"
        cached = self._get_cached_result(cache_key)
        if cached is not None:
            return cached

        result = self._check_room_action(user_id, room_id, action)
        self._cache_result(cache_key, result)
        return result

    @beartype
    def add_room_participant(self, room_id: str, user_id: UUID) -> Result[None, str]:
        """Add a user to a room's participant list."""
        # Check room capacity
        room_type = self._get_room_type(room_id)
        if room_type and room_type in self._access_rules:
            rule = self._access_rules[room_type]
            if rule.max_participants is not None:
                current_count = len(self._room_participants.get(room_id, set()))
                if current_count >= rule.max_participants:
                    return Err(
                        f"Room {room_id} is at maximum capacity ({rule.max_participants})"
                    )

        # Add participant
        if room_id not in self._room_participants:
            self._room_participants[room_id] = set()

        self._room_participants[room_id].add(user_id)
        return Ok(None)

    @beartype
    def remove_room_participant(self, room_id: str, user_id: UUID) -> None:
        """Remove a user from a room's participant list."""
        if room_id in self._room_participants:
            self._room_participants[room_id].discard(user_id)
            if not self._room_participants[room_id]:
                del self._room_participants[room_id]

    @beartype
    def get_room_participants(self, room_id: str) -> set[UUID]:
        """Get all participants in a room."""
        return self._room_participants.get(room_id, set()).copy()

    @beartype
    def get_user_accessible_rooms(self, user_id: UUID) -> list[str]:
        """Get all rooms a user can access."""
        accessible_rooms = []

        user_perms = self._user_permissions.get(user_id)
        if user_perms:
            for room_id in user_perms.room_permissions.keys():
                if self.can_user_access_room(user_id, room_id):
                    accessible_rooms.append(room_id)

        # Check owned rooms
        for room_id, owner_id in self._room_owners.items():
            if owner_id == user_id and room_id not in accessible_rooms:
                accessible_rooms.append(room_id)

        return accessible_rooms

    @beartype
    def cleanup_expired_permissions(self) -> int:
        """Clean up expired permissions and return count of removed permissions."""
        removed_count = 0

        for room_id, permissions in self._room_permissions.items():
            valid_permissions = [p for p in permissions if p.is_valid()]
            removed_count += len(permissions) - len(valid_permissions)
            self._room_permissions[room_id] = valid_permissions

        # Clear cache after cleanup
        self._permission_cache.clear()

        logger.info(f"Cleaned up {removed_count} expired permissions")
        return removed_count

    def _check_room_access(self, user_id: UUID, room_id: str) -> bool:
        """Internal method to check room access."""
        user_perms = self._user_permissions.get(user_id)
        if not user_perms or not user_perms.is_active:
            return False

        # Check if user is room owner
        if self._room_owners.get(room_id) == user_id:
            return True

        # Get room type and access rules
        room_type = self._get_room_type(room_id)
        if not room_type or room_type not in self._access_rules:
            return False

        rule = self._access_rules[room_type]

        # Check public read access
        if rule.allow_public_read:
            return True

        # Check user role
        if user_perms.role.value < rule.required_role.value:
            return False

        # Check required permissions
        if rule.required_permissions:
            room_perms = user_perms.room_permissions.get(room_id, [])
            for required_perm in rule.required_permissions:
                if required_perm not in room_perms:
                    return False

        return True

    def _check_room_action(
        self, user_id: UUID, room_id: str, action: PermissionType
    ) -> bool:
        """Internal method to check if user can perform action in room."""
        # First check if user can access room
        if not self.can_user_access_room(user_id, room_id):
            return False

        user_perms = self._user_permissions.get(user_id)
        if not user_perms:
            return False

        # Check if user is room owner (owners can do anything)
        if self._room_owners.get(room_id) == user_id:
            return True

        # Check specific room permission
        room_perms = user_perms.room_permissions.get(room_id, [])
        return action in room_perms

    def _get_room_type(self, room_id: str) -> RoomType | None:
        """Extract room type from room ID."""
        parts = room_id.split(":", 1)
        if len(parts) < 2:
            return None

        room_type_str = parts[0]
        try:
            return RoomType(room_type_str)
        except ValueError:
            return None

    def _get_cached_result(self, cache_key: str) -> bool | None:
        """Get cached permission result."""
        if cache_key in self._permission_cache:
            cache_entry = self._permission_cache[cache_key]
            if datetime.now() - cache_entry["timestamp"] < timedelta(
                seconds=self._cache_ttl
            ):
                result = cache_entry["result"]
                if isinstance(result, bool):
                    return result
            else:
                del self._permission_cache[cache_key]
        return None

    def _cache_result(self, cache_key: str, result: bool) -> None:
        """Cache permission result."""
        self._permission_cache[cache_key] = {
            "result": result,
            "timestamp": datetime.now(),
        }

    def _clear_user_cache(self, user_id: UUID) -> None:
        """Clear cache entries for a specific user."""
        keys_to_remove = [
            key for key in self._permission_cache.keys() if str(user_id) in key
        ]
        for key in keys_to_remove:
            del self._permission_cache[key]

    def _clear_room_cache(self, room_id: str) -> None:
        """Clear cache entries for a specific room."""
        keys_to_remove = [
            key for key in self._permission_cache.keys() if room_id in key
        ]
        for key in keys_to_remove:
            del self._permission_cache[key]

    @beartype
    def get_permission_summary(self) -> dict[str, Any]:
        """Get summary of all permissions."""
        return {
            "total_users": len(self._user_permissions),
            "total_rooms_with_permissions": len(self._room_permissions),
            "total_room_owners": len(self._room_owners),
            "total_room_participants": sum(
                len(participants) for participants in self._room_participants.values()
            ),
            "cache_entries": len(self._permission_cache),
            "access_rules": {
                room_type.value: rule.model_dump()
                for room_type, rule in self._access_rules.items()
            },
        }
