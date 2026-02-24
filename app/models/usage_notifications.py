from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UsageNotification(Base):
    __tablename__ = "usage_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    slab_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )
