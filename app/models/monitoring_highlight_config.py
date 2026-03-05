from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    SmallInteger,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MonitoringHighlightConfig(Base):
    __tablename__ = "monitoring_highlight_config"
    __table_args__ = (
        CheckConstraint(
            "frustration_min_threshold BETWEEN 1 AND 10",
            name="ck_monitoring_highlight_config_frustration_min_threshold_range",
        ),
        CheckConstraint(
            "accuracy_max_threshold BETWEEN 1 AND 10",
            name="ck_monitoring_highlight_config_accuracy_max_threshold_range",
        ),
        CheckConstraint(
            "unresolved_satisfaction_max_threshold BETWEEN 1 AND 10",
            name="ck_monitoring_highlight_config_unresolved_satisfaction_max_threshold_range",
        ),
        Index(
            "uq_monitoring_highlight_config_single_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    frustration_min_threshold: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default="7"
    )
    failure_escalation_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    loop_detected_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    accuracy_max_threshold: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default="3"
    )
    unresolved_low_satisfaction_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    unresolved_satisfaction_max_threshold: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default="3"
    )
    user_irrelevancy_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
