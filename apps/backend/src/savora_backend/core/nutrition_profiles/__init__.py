"""User profile and nutrition target entities, DTOs, repository, service, and routes."""

import asyncio
import json
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import Field
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Uuid, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from savora_ai.core.nutrition.models import NutritionTargets, TargetInput
from savora_ai.core.nutrition.targets import calculate_nutrition_targets
from savora_ai.core.pipelines import (
    CatalogueBundle,
    DietPattern,
    PlanningProfile,
    revalidate_seeds,
)
from savora_ai.core.recommendation.seeds import MIN_SEED_PICKS
from savora_ai.schemas.enums import ActivityLevel, CuisinePolicy, Goal, HealthCondition, Sex
from savora_backend.auth import CurrentUser
from savora_backend.core.catalogue import get_catalogue_bundle
from savora_backend.core.common import CamelModel
from savora_backend.database import CommonEntity, JsonbType, StringArrayType, get_session
from savora_backend.decorators import response_message
from savora_backend.exceptions import RuntimeException, ValidationException
from savora_backend.interceptors import TransformRoute


class UserProfileEntity(CommonEntity):
    __tablename__ = "user_profiles"

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
    __tablename__ = "user_nutrition_profiles"

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    formula_version: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    targets: Mapped[dict[str, Any]] = mapped_column(JsonbType, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProfileUpsertRequest(CamelModel):
    age_years: int = Field(ge=19, le=100)
    sex: Sex
    height_cm: float = Field(ge=100, le=250)
    weight_kg: float = Field(ge=30, le=300)
    activity: ActivityLevel
    goal: Goal
    diet: DietPattern | None = None
    cuisine_policy: CuisinePolicy = CuisinePolicy.MIXED
    cuisines: list[str] = Field(default_factory=list, max_length=25)
    excluded_ingredients: list[str] = Field(default_factory=list, max_length=50)
    allergies: list[str] = Field(default_factory=list, max_length=50)
    allergies_confirmed: bool = False
    conditions: list[HealthCondition] = Field(default_factory=list, max_length=10)


class UserProfileDto(CamelModel):
    id: UUID
    user_id: UUID
    version: int
    age_years: int
    sex: Sex
    height_cm: float
    weight_kg: float
    activity: ActivityLevel
    goal: Goal
    diet: DietPattern | None
    cuisine_policy: CuisinePolicy
    cuisines: list[str]
    excluded_ingredients: list[str]
    allergies: list[str]
    allergies_confirmed_at: datetime | None
    conditions: list[HealthCondition]
    seed_recipe_ids: list[str]


class ProfileEnvelopeData(CamelModel):
    profile: UserProfileDto
    targets: NutritionTargets
    needs_seed_picks: bool


def to_planning_profile(entity: UserProfileEntity) -> PlanningProfile:
    return PlanningProfile(
        profile_id=str(entity.user_id),
        profile_version=entity.version,
        diet=DietPattern(entity.diet) if entity.diet else None,
        cuisine_policy=CuisinePolicy(entity.cuisine_policy),
        cuisines=tuple(entity.cuisines),
        excluded_ingredients=tuple(entity.excluded_ingredients),
        allergies=tuple(entity.allergies),
        conditions=tuple(HealthCondition(c) for c in entity.conditions),
        seed_recipe_ids=tuple(entity.seed_recipe_ids[:5]),
    )


def _clean_word_list(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    for val in values:
        token = " ".join(val.strip().split())
        if token and token not in cleaned:
            cleaned.append(token)
    return cleaned


class ProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: UUID) -> UserProfileEntity | None:
        stmt = select(UserProfileEntity).where(UserProfileEntity.user_id == user_id)
        return await self._session.scalar(stmt)

    async def get_latest_nutrition(
        self, user_id: UUID, profile_version: int
    ) -> UserNutritionProfileEntity | None:
        stmt = (
            select(UserNutritionProfileEntity)
            .where(
                UserNutritionProfileEntity.user_id == user_id,
                UserNutritionProfileEntity.profile_version == profile_version,
            )
            .order_by(desc(UserNutritionProfileEntity.created_at))
        )
        return await self._session.scalar(stmt)

    async def save_profile(self, profile: UserProfileEntity) -> UserProfileEntity:
        self._session.add(profile)
        await self._session.flush()
        return profile

    async def save_nutrition_snapshot(
        self, snapshot: UserNutritionProfileEntity
    ) -> UserNutritionProfileEntity:
        self._session.add(snapshot)
        await self._session.flush()
        return snapshot


class ProfileService:
    def __init__(
        self,
        session: AsyncSession,
        bundle: CatalogueBundle | None = None,
    ) -> None:
        self._repo = ProfileRepository(session)
        self._bundle = bundle or get_catalogue_bundle()

    async def get_profile(self, user_id: UUID) -> ProfileEnvelopeData:
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise RuntimeException(
                "Profile not found; complete onboarding first",
                status_code=status.HTTP_404_NOT_FOUND,
                source="profile",
            )
        snapshot = await self._repo.get_latest_nutrition(user_id, profile.version)
        if snapshot is None:
            raise RuntimeException(
                "Nutrition target snapshot not found",
                status_code=status.HTTP_404_NOT_FOUND,
                source="profile",
            )
        targets = NutritionTargets.model_validate_json(json.dumps(snapshot.targets))
        needs_seeds = len(profile.seed_recipe_ids) < MIN_SEED_PICKS
        return ProfileEnvelopeData(
            profile=UserProfileDto.model_validate(profile),
            targets=targets,
            needs_seed_picks=needs_seeds,
        )

    async def upsert_profile(
        self, user_id: UUID, body: ProfileUpsertRequest
    ) -> ProfileEnvelopeData:
        allergies = _clean_word_list(body.allergies)
        if allergies and not body.allergies_confirmed:
            raise ValidationException(
                {
                    "allergiesConfirmed": [
                        "Explicit confirmation is required when allergies are set"
                    ]
                },
                source="profile",
            )
        cuisines = _clean_word_list(body.cuisines)
        if body.cuisine_policy is CuisinePolicy.STRICT and not cuisines:
            raise ValidationException(
                {"cuisines": ["At least one cuisine is required when cuisinePolicy is STRICT"]},
                source="profile",
            )
        known_cuisines = set(self._bundle.cuisine_ids.values())
        unknown_cuisines = [c for c in cuisines if c not in known_cuisines]
        if unknown_cuisines:
            raise ValidationException(
                {"cuisines": [f"Unknown catalogue cuisine(s): {', '.join(unknown_cuisines)}"]},
                source="profile",
            )
        exclusions = _clean_word_list(body.excluded_ingredients)
        conditions = list(dict.fromkeys(c.value for c in body.conditions))
        now = datetime.now(UTC)

        existing = await self._repo.get_by_user_id(user_id)
        if existing is None:
            new_version = 1
            profile = UserProfileEntity(
                user_id=user_id,
                version=new_version,
                age_years=body.age_years,
                sex=body.sex.value,
                height_cm=body.height_cm,
                weight_kg=body.weight_kg,
                activity=body.activity.value,
                goal=body.goal.value,
                diet=body.diet.value if body.diet else None,
                cuisine_policy=body.cuisine_policy.value,
                cuisines=cuisines,
                excluded_ingredients=exclusions,
                allergies=allergies,
                allergies_confirmed_at=now if allergies else None,
                conditions=conditions,
                seed_recipe_ids=[],
            )
        else:
            new_version = existing.version + 1
            existing.version = new_version
            existing.age_years = body.age_years
            existing.sex = body.sex.value
            existing.height_cm = body.height_cm
            existing.weight_kg = body.weight_kg
            existing.activity = body.activity.value
            existing.goal = body.goal.value
            existing.diet = body.diet.value if body.diet else None
            existing.cuisine_policy = body.cuisine_policy.value
            existing.cuisines = cuisines
            existing.excluded_ingredients = exclusions
            existing.allergies = allergies
            existing.allergies_confirmed_at = now if allergies else None
            existing.conditions = conditions
            profile = existing

        if profile.seed_recipe_ids:
            planning_prof = to_planning_profile(profile)
            valid_seeds = await asyncio.to_thread(
                revalidate_seeds, planning_prof, self._bundle
            )
            profile.seed_recipe_ids = list(valid_seeds)

        await self._repo.save_profile(profile)

        target_input = TargetInput(
            age_years=body.age_years,
            sex=body.sex,
            height_cm=body.height_cm,
            weight_kg=body.weight_kg,
            activity=body.activity,
            goal=body.goal,
        )
        targets = calculate_nutrition_targets(
            target_input,
            profile_version=new_version,
            calculated_at=now,
        )
        snapshot = UserNutritionProfileEntity(
            user_id=user_id,
            profile_version=new_version,
            formula_version=targets.formula_version,
            input_hash=targets.input_hash,
            targets=targets.model_dump(mode="json", by_alias=True),
            calculated_at=now,
        )
        await self._repo.save_nutrition_snapshot(snapshot)

        needs_seeds = len(profile.seed_recipe_ids) < MIN_SEED_PICKS
        return ProfileEnvelopeData(
            profile=UserProfileDto.model_validate(profile),
            targets=targets,
            needs_seed_picks=needs_seeds,
        )


profile_router = APIRouter(
    prefix="/profile",
    tags=["profile"],
    route_class=TransformRoute,
)


@profile_router.get("")
@response_message("Profile retrieved")
async def get_profile(
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProfileEnvelopeData:
    return await ProfileService(session).get_profile(user.id)


@profile_router.put("")
@response_message("Profile saved")
async def put_profile(
    body: ProfileUpsertRequest,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProfileEnvelopeData:
    return await ProfileService(session).upsert_profile(user.id, body)
