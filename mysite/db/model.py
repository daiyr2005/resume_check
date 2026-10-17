from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy_file import File, FileField

from mysite.db.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, Enum):
    JUNIOR = "junior"
    MIDDLE = "middle"
    SENIOR = "senior"
    LEADER = "leader"


class Info(Base):
    __tablename__ = "info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)  # хранить хеш
    role: Mapped[str] = mapped_column(String(20), default=UserRole.JUNIOR.value, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    resume: Mapped[File | None] = mapped_column(FileField, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="token_user",
        cascade="all, delete-orphan",
    )

    def __str__(self) -> str:
        return self.full_name


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("info.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(512), nullable=False)
    created_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    token_user: Mapped["Info"] = relationship(back_populates="refresh_tokens")

    def __repr__(self) -> str:
        return self.token