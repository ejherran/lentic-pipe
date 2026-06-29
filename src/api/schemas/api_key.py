import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from src.api.models.api_key import ApiKeyScope


class ApiKeyCreateRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {"name": "notebook-script", "expires_days": 90, "scope": "full"}
        }
    }

    name: str = Field(min_length=1, max_length=100)
    expires_days: int | None = Field(default=None, ge=1, le=3650)
    scope: ApiKeyScope = ApiKeyScope.full


class ApiKeyCreatedResponse(BaseModel):
    """Returned only once at creation — includes the raw key."""
    id: uuid.UUID
    name: str
    key: str
    key_prefix: str
    scope: ApiKeyScope
    expires_at: datetime | None
    created_at: datetime


class ApiKeyResponse(BaseModel):
    """Returned on list/get — raw key is never re-exposed."""
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    key_prefix: str
    scope: ApiKeyScope
    is_active: bool
    last_used_at: datetime | None
    expires_at: datetime | None
    created_at: datetime
