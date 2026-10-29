from pydantic import BaseModel
from mysite.db.model import *
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from mysite.db.model import UserRole  # поправьте путь под ваш проект


class ResumeOut(BaseModel):
    filename: str | None = None
    content_type: str | None = None
    size: int | None = None
    url: str | None = None


class InfoBase(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    email: EmailStr


class InfoCreate(InfoBase):
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.JUNIOR


class InfoUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=150)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: UserRole | None = None
    is_active: bool | None = None


class InfoOut(InfoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: UserRole
    is_active: bool
    resume: ResumeOut | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("resume", mode="before")
    @classmethod
    def convert_resume(cls, v: Any):
        # sqlalchemy_file.File ведёт себя как dict
        if v is None:
            return None
        return {
            "filename": v.get("filename"),
            "content_type": v.get("content_type"),
            "size": v.get("size"),
            "url": v.get("url"),
        }


class LoginSchema(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenIn(BaseModel):
    refresh_token: str


class RefreshTokenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_date: datetime

class MessageOut(BaseModel):
    message: str


from pydantic import BaseModel, Field


class CheckTextIn(BaseModel):
    resume: str = Field(min_length=50, max_length=20000)
    vacancy: str = Field(default="", max_length=12000)
    vacancy: str = Field(default="", max_length=12000)


class CheckOut(BaseModel):
    suitable: bool
    answer: str


class CheckUserOut(CheckOut):
    user_id: int
    user: str
