"""Profile upsert with versioned nutrition targets (section 4.1)."""

import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from savora_ai.core.nutrition.models import NutritionTargets, TargetInput
from savora_ai.core.nutrition.targets import calculate_nutrition_targets
from savora_ai.core.pipelines import CatalogueBundle, revalidate_seeds
from savora_ai.core.recommendation.seeds import MIN_SEED_PICKS
from savora_ai.schemas.enums import CuisinePolicy
from savora_backend.core.nutrition_profiles.dto import (
    ProfileEnvelopeData,
    ProfileUpsertRequest,
    UserProfileDto,
)
from savora_backend.core.nutrition_profiles.entity import (
    UserNutritionProfileEntity,
    UserProfileEntity,
)
from savora_backend.core.nutrition_profiles.mapper import to_planning_profile
from savora_backend.core.nutrition_profiles.repository import ProfileRepository
from savora_backend.exceptions import RuntimeException, ValidationException

SOURCE = "profile"


def _clean_word_list(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    for val in values:
        token = " ".join(val.strip().split())
        if token and token not in cleaned:
            cleaned.append(token)
    return cleaned


def _not_found(message: str) -> RuntimeException:
    return RuntimeException(message, status_code=status.HTTP_404_NOT_FOUND, source=SOURCE)


class ProfileService:
    def __init__(self, session: AsyncSession, bundle: CatalogueBundle) -> None:
        self._repo = ProfileRepository(session)
        self._bundle = bundle

    async def get_profile(self, user_id: UUID) -> ProfileEnvelopeData:
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise _not_found("Profile not found; complete onboarding first")
        snapshot = await self._repo.get_latest_nutrition(user_id, profile.version)
        if snapshot is None:
            raise _not_found("Nutrition target snapshot not found")
        return self._envelope(
            profile, NutritionTargets.model_validate_json(json.dumps(snapshot.targets))
        )

    def _envelope(
        self, profile: UserProfileEntity, targets: NutritionTargets
    ) -> ProfileEnvelopeData:
        return ProfileEnvelopeData(
            profile=UserProfileDto.model_validate(profile),
            targets=targets,
            needs_seed_picks=len(profile.seed_recipe_ids) < MIN_SEED_PICKS,
        )

    def _validated_fields(self, body: ProfileUpsertRequest) -> dict[str, Any]:
        allergies = _clean_word_list(body.allergies)
        if allergies and not body.allergies_confirmed:
            raise ValidationException(
                {
                    "allergiesConfirmed": [
                        "Explicit confirmation is required when allergies are set"
                    ]
                },
                source=SOURCE,
            )
        cuisines = _clean_word_list(body.cuisines)
        if body.cuisine_policy is CuisinePolicy.STRICT and not cuisines:
            raise ValidationException(
                {"cuisines": ["At least one cuisine is required when cuisinePolicy is STRICT"]},
                source=SOURCE,
            )
        unknown = [c for c in cuisines if c not in set(self._bundle.target_cuisine_ids.values())]
        if unknown:
            raise ValidationException(
                {"cuisines": [f"Unknown catalogue cuisine(s): {', '.join(unknown)}"]},
                source=SOURCE,
            )
        return {
            "age_years": body.age_years,
            "sex": body.sex.value,
            "height_cm": body.height_cm,
            "weight_kg": body.weight_kg,
            "activity": body.activity.value,
            "goal": body.goal.value,
            "diet": body.diet.value if body.diet else None,
            "cuisine_policy": body.cuisine_policy.value,
            "cuisines": cuisines,
            "excluded_ingredients": _clean_word_list(body.excluded_ingredients),
            "allergies": allergies,
            "conditions": list(dict.fromkeys(c.value for c in body.conditions)),
        }

    async def upsert_profile(
        self, user_id: UUID, body: ProfileUpsertRequest
    ) -> ProfileEnvelopeData:
        fields = self._validated_fields(body)
        now = datetime.now(UTC)
        profile = await self._repo.get_by_user_id(user_id)
        if profile is not None and all(getattr(profile, k) == v for k, v in fields.items()):
            # Nothing relevant changed: same version, same targets, plans stay valid.
            return await self.get_profile(user_id)
        if profile is None:
            profile = UserProfileEntity(user_id=user_id, version=1, seed_recipe_ids=[], **fields)
            profile.allergies_confirmed_at = now if fields["allergies"] else None
        else:
            allergies_changed = profile.allergies != fields["allergies"]
            for key, value in fields.items():
                setattr(profile, key, value)
            profile.version += 1
            if allergies_changed:
                profile.allergies_confirmed_at = now if fields["allergies"] else None
        if profile.seed_recipe_ids:
            profile.seed_recipe_ids = list(
                await asyncio.to_thread(
                    revalidate_seeds, to_planning_profile(profile), self._bundle
                )
            )
        await self._repo.save_profile(profile)
        targets = calculate_nutrition_targets(
            TargetInput(
                age_years=body.age_years,
                sex=body.sex,
                height_cm=body.height_cm,
                weight_kg=body.weight_kg,
                activity=body.activity,
                goal=body.goal,
            ),
            profile_version=profile.version,
            calculated_at=now,
        )
        await self._repo.save_nutrition_snapshot(
            UserNutritionProfileEntity(
                user_id=user_id,
                profile_version=profile.version,
                formula_version=targets.formula_version,
                input_hash=targets.input_hash,
                targets=targets.model_dump(mode="json", by_alias=True),
                calculated_at=now,
            )
        )
        return self._envelope(profile, targets)
