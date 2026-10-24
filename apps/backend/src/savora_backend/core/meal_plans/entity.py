"""Weekly plan, slot and substitution ORM entities (sections 4.2, 4.4 and 10)."""

from datetime import date
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from savora_backend.database import CommonEntity, JsonbType, StringArrayType


class MealPlanJobStatus(StrEnum):
    GENERATING = "GENERATING"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    TIMEOUT = "TIMEOUT"
    FAILED = "FAILED"


_GENERATING = text("status = 'GENERATING'")

PLAN_TIMEOUT_MESSAGE = "Generation timed out. Please try again."
SWAP_TIMEOUT_MESSAGE = "Substitution timed out. Please try again."
CANCELLED_MESSAGE = "Generation cancelled by user."


class MealPlanEntity(CommonEntity):
    __tablename__ = "meal_plans"
    __table_args__ = (
        Index("ix_meal_plans_user_current", "user_id", "is_current"),
        Index("ix_meal_plans_user_week_start", "user_id", "week_start"),
        # At most one generating plan per user, enforced by the database (migration 0005).
        Index(
            "uq_meal_plans_user_generating",
            "user_id",
            unique=True,
            postgresql_where=_GENERATING,
            sqlite_where=_GENERATING,
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=MealPlanJobStatus.GENERATING.value, nullable=False
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    catalogue_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fallback_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kb_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kb_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    safety: Mapped[dict[str, Any] | None] = mapped_column(JsonbType, nullable=True)
    search: Mapped[dict[str, Any] | None] = mapped_column(JsonbType, nullable=True)
    day_totals: Mapped[list[dict[str, Any]] | None] = mapped_column(JsonbType, nullable=True)
    # Server-only provenance, not VERIFIED_AT_SAVE or client-supplied authority.
    source_binding: Mapped[dict[str, Any] | None] = mapped_column(JsonbType, nullable=True)
    parent_plan_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("meal_plans.id", ondelete="SET NULL"), nullable=True
    )
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class MealPlanSlotEntity(CommonEntity):
    __tablename__ = "meal_plan_slots"
    __table_args__ = (UniqueConstraint("plan_id", "slot_id", name="uq_meal_plan_slots_plan_slot"),)

    plan_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("meal_plans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    slot_id: Mapped[str] = mapped_column(String(32), nullable=False)
    day_index: Mapped[int] = mapped_column(Integer, nullable=False)
    calendar_date: Mapped[str] = mapped_column(String(16), nullable=False)
    meal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    option_id: Mapped[str] = mapped_column(String(255), nullable=False)
    combination_id: Mapped[str] = mapped_column(String(255), nullable=False)
    configuration_id: Mapped[str] = mapped_column(String(255), nullable=False)
    preset: Mapped[str] = mapped_column(String(32), nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JsonbType, nullable=False)


class MealPlanSubstitutionEntity(CommonEntity):
    __tablename__ = "meal_plan_substitutions"
    __table_args__ = (
        Index(
            "uq_meal_plan_substitutions_user_generating",
            "user_id",
            unique=True,
            postgresql_where=_GENERATING,
            sqlite_where=_GENERATING,
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    from_plan_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("meal_plans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    to_plan_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("meal_plans.id", ondelete="SET NULL"), nullable=True
    )
    slot_id: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=MealPlanJobStatus.GENERATING.value, nullable=False
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    before_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JsonbType, nullable=True)
    after_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JsonbType, nullable=True)
    excluded_combination_ids: Mapped[list[str]] = mapped_column(
        StringArrayType, default=list, nullable=False
    )
    # The option the user picked (suggest_replacements), if any, and the validated
    # CravingRequest their words were parsed into; never the raw text (no chat history).
    replacement_combination_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preference: Mapped[dict[str, Any] | None] = mapped_column(JsonbType, nullable=True)
    # Member 2's compact B1 proof of the swap (`SwapProof`): its decision, the certificate
    # digest binding the independently reconstructed witness, and the changed day's totals.
    proof_certificate_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    proof: Mapped[dict[str, Any] | None] = mapped_column(JsonbType, nullable=True)
