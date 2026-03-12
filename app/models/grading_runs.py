from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base
from app.models.enums import IdentityType, normalize_identity_type


class GradingRunTriggerType(str, Enum):
    SCHEDULED = "scheduled"
    MANUAL = "manual"


class GradingRunMode(str, Enum):
    DAILY = "daily"
    BACKFILL = "backfill"
    RERUN = "rerun"


class GradingRunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_FAILURES = "completed_with_failures"
    FAILED = "failed"


class GradingRunItemStatus(str, Enum):
    SUCCESS = "success"
    SKIPPED_EXISTING = "skipped_existing"
    EMPTY_TRANSCRIPT = "empty_transcript"
    PROVIDER_ERROR = "provider_error"
    PARSE_ERROR = "parse_error"


_RUN_TRIGGER_TYPE_VALUES = tuple(item.value for item in GradingRunTriggerType)
_RUN_MODE_VALUES = tuple(item.value for item in GradingRunMode)
_RUN_STATUS_VALUES = tuple(item.value for item in GradingRunStatus)
_RUN_ITEM_STATUS_VALUES = tuple(item.value for item in GradingRunItemStatus)


def _normalize_literal(
    value: str | None,
    *,
    allowed_values: tuple[str, ...],
    field_name: str,
) -> str | None:
    if value is None:
        return None

    normalized = value.strip().lower()
    if not normalized:
        return None
    if normalized not in allowed_values:
        raise ValueError(f"Unsupported {field_name} value: {value!r}")
    return normalized


def _validate_non_negative_int(value: int | None, *, field_name: str) -> int | None:
    if value is None:
        return None
    if value < 0:
        raise ValueError(f"{field_name} must be greater than or equal to 0.")
    return value


class GradingRun(Base):
    __tablename__ = "grading_runs"
    __table_args__ = (
        CheckConstraint(
            "trigger_type IN ('scheduled', 'manual')",
            name="trigger_type_values",
        ),
        CheckConstraint(
            "run_mode IN ('daily', 'backfill', 'rerun')",
            name="run_mode_values",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', "
            "'completed_with_failures', 'failed')",
            name="status_values",
        ),
        CheckConstraint(
            "target_start_date <= target_end_date",
            name="target_window_order",
        ),
        CheckConstraint("candidate_count >= 0", name="candidate_count_non_negative"),
        CheckConstraint("attempted_count >= 0", name="attempted_count_non_negative"),
        CheckConstraint("success_count >= 0", name="success_count_non_negative"),
        CheckConstraint(
            "skipped_existing_count >= 0",
            name="skipped_existing_count_non_negative",
        ),
        CheckConstraint(
            "empty_transcript_count >= 0",
            name="empty_transcript_count_non_negative",
        ),
        CheckConstraint(
            "provider_error_count >= 0",
            name="provider_error_count_non_negative",
        ),
        CheckConstraint(
            "parse_error_count >= 0",
            name="parse_error_count_non_negative",
        ),
        Index("ix_grading_runs_status_created_at", "status", "created_at"),
        Index(
            "ix_grading_runs_target_window_status",
            "target_start_date",
            "target_end_date",
            "status",
        ),
        Index("ix_grading_runs_requested_by_account_id", "requested_by_account_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    trigger_type: Mapped[str] = mapped_column(String(16), nullable=False)
    run_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    target_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    target_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    rerun_existing: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    attempted_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    success_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    skipped_existing_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    empty_transcript_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    provider_error_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    parse_error_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    requested_by_account_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    items: Mapped[list["GradingRunItem"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @validates("trigger_type")
    def _validate_trigger_type(self, _key: str, value: str | None) -> str | None:
        return _normalize_literal(
            value,
            allowed_values=_RUN_TRIGGER_TYPE_VALUES,
            field_name="trigger_type",
        )

    @validates("run_mode")
    def _validate_run_mode(self, _key: str, value: str | None) -> str | None:
        return _normalize_literal(
            value,
            allowed_values=_RUN_MODE_VALUES,
            field_name="run_mode",
        )

    @validates("status")
    def _validate_status(self, _key: str, value: str | None) -> str | None:
        return _normalize_literal(
            value,
            allowed_values=_RUN_STATUS_VALUES,
            field_name="status",
        )

    @validates(
        "candidate_count",
        "attempted_count",
        "success_count",
        "skipped_existing_count",
        "empty_transcript_count",
        "provider_error_count",
        "parse_error_count",
    )
    def _validate_counter(self, key: str, value: int | None) -> int | None:
        return _validate_non_negative_int(value, field_name=key)

    @property
    def trigger_type_enum(self) -> GradingRunTriggerType:
        return GradingRunTriggerType(self.trigger_type)

    @property
    def run_mode_enum(self) -> GradingRunMode:
        return GradingRunMode(self.run_mode)

    @property
    def status_enum(self) -> GradingRunStatus:
        return GradingRunStatus(self.status)


class GradingRunItem(Base):
    __tablename__ = "grading_run_items"
    __table_args__ = (
        CheckConstraint(
            "identity_type IN ('phone', 'email', 'session')",
            name="identity_type_values",
        ),
        CheckConstraint(
            "status IN ('success', 'skipped_existing', 'empty_transcript', "
            "'provider_error', 'parse_error')",
            name="status_values",
        ),
        UniqueConstraint(
            "run_id",
            "identity_type",
            "conversation_identity",
            "grade_date",
            name="uq_grading_run_items_run_candidate",
        ),
        Index("ix_grading_run_items_run_id_status", "run_id", "status"),
        Index("ix_grading_run_items_run_id_grade_date", "run_id", "grade_date"),
        Index("ix_grading_run_items_grade_id", "grade_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("grading_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    identity_type: Mapped[str] = mapped_column(String(16), nullable=False)
    conversation_identity: Mapped[str] = mapped_column(String(255), nullable=False)
    grade_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    grade_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("conversation_grades.id", ondelete="SET NULL"),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_details: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    run: Mapped[GradingRun] = relationship(back_populates="items")

    @validates("identity_type")
    def _validate_identity_type(self, _key: str, value: Any) -> str | None:
        normalized = normalize_identity_type(value)
        if normalized is None:
            raise ValueError(f"Unsupported identity_type value: {value!r}")
        return normalized.value

    @validates("status")
    def _validate_status(self, _key: str, value: str | None) -> str | None:
        return _normalize_literal(
            value,
            allowed_values=_RUN_ITEM_STATUS_VALUES,
            field_name="status",
        )

    @property
    def identity_type_enum(self) -> IdentityType | None:
        return normalize_identity_type(self.identity_type)

    @property
    def status_enum(self) -> GradingRunItemStatus:
        return GradingRunItemStatus(self.status)
