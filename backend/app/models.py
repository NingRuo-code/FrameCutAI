from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    file_path: Mapped[str] = mapped_column(String(1024))
    file_size: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(40), default="uploaded")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class TaskEvent(Base):
    __tablename__ = "task_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("videos.id", ondelete="CASCADE"),
        index=True,
    )
    stage: Mapped[str] = mapped_column(String(80))
    level: Mapped[str] = mapped_column(String(40), default="info")
    message: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
