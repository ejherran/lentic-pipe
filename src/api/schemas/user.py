import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from src.api.models.user import SystemRole


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: EmailStr
    username: str
    full_name: str | None
    system_role: SystemRole
    is_active: bool
    email_verified: bool
    created_at: datetime
    updated_at: datetime


class UserUpdateRequest(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None


class AdminUserUpdateRequest(UserUpdateRequest):
    system_role: SystemRole | None = None
    is_active: bool | None = None


class NotificationPreferencesResponse(BaseModel):
    model_config = {"from_attributes": True}

    notify_on_run_completed: bool
    notify_on_run_failed: bool
    notify_on_simulation_completed: bool
    notify_on_simulation_failed: bool


class NotificationPreferencesUpdateRequest(BaseModel):
    notify_on_run_completed: bool | None = None
    notify_on_run_failed: bool | None = None
    notify_on_simulation_completed: bool | None = None
    notify_on_simulation_failed: bool | None = None
