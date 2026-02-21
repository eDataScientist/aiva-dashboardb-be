from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, SmallInteger, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.db.base import Base
from app.models.enums import EscalationType, normalize_escalation_type


class ConversationGrade(Base):
    __tablename__ = "conversation_grades"
    __table_args__ = (
        UniqueConstraint(
            "phone_number",
            "grade_date",
            name="uq_conversation_grades_phone_number_grade_date",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    phone_number: Mapped[str] = mapped_column(String(64), nullable=False)
    grade_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

    relevancy_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    relevancy_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    accuracy_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    accuracy_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    completeness_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    completeness_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    clarity_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    clarity_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    tone_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    tone_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    resolution: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    resolution_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    repetition_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    repetition_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    loop_detected: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    loop_detected_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    satisfaction_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    satisfaction_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    frustration_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    frustration_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_relevancy: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    user_relevancy_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    escalation_occurred: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    escalation_occurred_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Keep as string in the initial model contract, then enforce enum in P1.1.3/P1.1.6.
    escalation_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    escalation_type_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    intent_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    intent_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    @validates("escalation_type")
    def _validate_escalation_type(self, _key: str, value: str | None) -> str | None:
        normalized = normalize_escalation_type(value)
        return None if normalized is None else normalized.value

    @property
    def escalation_type_enum(self) -> EscalationType | None:
        return normalize_escalation_type(self.escalation_type)
