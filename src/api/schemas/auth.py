import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "researcher@example.com",
                "username": "jherran",
                "password": "lentic2024!",
                "full_name": "Javier Herran",
            }
        }
    }

    email: EmailStr
    username: str
    password: str
    full_name: str | None = None

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username must be alphanumeric (hyphens and underscores allowed)")
        if len(v) < 3 or len(v) > 50:
            raise ValueError("Username must be between 3 and 50 characters")
        return v.lower()

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {"username": "jherran", "password": "lentic2024!"}
        }
    }

    username: str
    password: str


class RefreshRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0eXBlIjoicmVmcmVzaCJ9.SIGNATURE"
            }
        }
    }

    refresh_token: str


class TokenResponse(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.ACCESS.SIGNATURE",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.REFRESH.SIGNATURE",
                "token_type": "bearer",
            }
        }
    }

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "current_password": "lentic2024!",
                "new_password": "newSecurePass99!",
            }
        }
    }

    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class PasswordResetRequest(BaseModel):
    model_config = {"json_schema_extra": {"example": {"email": "researcher@example.com"}}}
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "researcher@example.com",
                "code": "382910",
                "new_password": "newSecurePass99!",
            }
        }
    }

    email: EmailStr
    code: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class SessionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    created_at: datetime
    expires_at: datetime
    is_revoked: bool
