"""Profile and versioned nutrition-target ORM entities."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from savora_ai.schemas.enums import CuisinePolicy
from savora_backend.database import CommonEntity, JsonbType, StringArrayType


class UserProfileEntity(CommonEntity):
    __tablename__ = "user_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_profiles_user_id"),)

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    age_years: Mapped[int] = mapped_column(Integer, nullable=False)
    sex: Mapped[str] = mapped_column(String(16), nullable=False)
    height_cm: Mapped[float] = mapped_column(Float, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    activity: Mapped[str] = mapped_column(String(32), nullable=False)
    goal: Mapped[str] = mapped_column(String(32), nullable=False)
    diet: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cuisine_policy: Mapped[str] = mapped_column(
        String(32), default=CuisinePolicy.MIXED.value, nullable=False
    )
    cuisines: Mapped[list[str]] = mapped_column(StringArrayType, default=list, nullable=False)
    excluded_ingredients: Mapped[list[str]] = mapped_column(
        StringArrayType, default=list, nullable=False
    )
    allergies: Mapped[list[str]] = mapped_column(StringArrayType, default=list, nullable=False)
    allergies_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    conditions: Mapped[list[str]] = mapped_column(StringArrayType, default=list, nullable=False)
    seed_recipe_ids: Mapped[list[str]] = mapped_column(
        StringArrayType, default=list, nullable=False
    )


class UserNutritionProfileEntity(CommonEntity):
    """One immutable target snapshot per profile version (section 4.1 step 5)."""

    __tablename__ = "user_nutrition_profiles"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "profile_version", name="uq_user_nutrition_profiles_user_version"
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    formula_version: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    targets: Mapped[dict[str, Any]] = mapped_column(JsonbType, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
