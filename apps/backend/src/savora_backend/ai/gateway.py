"""Async AI gateway protocol and real pipeline adapter."""

import asyncio
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from typing import Annotated, Protocol

from fastapi import Depends

from savora_ai.core.craving_nlu import CravingParser
from savora_ai.core.pipelines import (
    CatalogueBundle,
    CravingRecommendation,
    PlanningProfile,
    ReplacementOptions,
    WeekPlan,
    confirm_seeds,
    plan_week,
    recommend_for_craving,
    revalidate_seeds,
    substitute_slot,
    suggest_replacements,
    suggest_seeds,
)
from savora_ai.core.recommendation.seeds import DEFAULT_SUGGESTIONS, SeedSuggestions
from savora_ai.schemas.craving import CravingRequest
from savora_backend.ai.runtime import AiRuntime, get_ai_runtime


class AiGateway(Protocol):
    @property
    def bundle(self) -> CatalogueBundle: ...

    async def craving(
        self,
        request: CravingRequest,
        profile: PlanningProfile,
        *,
        top_k: int = 10,
    ) -> CravingRecommendation: ...

    async def plan_week(
        self,
        profile: PlanningProfile,
        *,
        week_id: str,
        start_date: date,
    ) -> WeekPlan: ...

    async def substitute(
        self,
        profile: PlanningProfile,
        *,
        current: Mapping[str, str],
        slot: str,
        week_id: str,
        start_date: date,
        exclude_combination_ids: Iterable[str] = (),
        replacement_combination_id: str | None = None,
        preference: CravingRequest | None = None,
    ) -> WeekPlan: ...

    async def replacements(
        self,
        profile: PlanningProfile,
        *,
        current: Mapping[str, str],
        slot: str,
        preference: CravingRequest | None = None,
        exclude_combination_ids: Iterable[str] = (),
        limit: int = 6,
    ) -> ReplacementOptions: ...

    async def seeds(
        self,
        profile: PlanningProfile,
        *,
        limit: int = DEFAULT_SUGGESTIONS,
    ) -> SeedSuggestions: ...

    async def confirm_seeds(
        self,
        profile: PlanningProfile,
        picks: Sequence[str],
    ) -> tuple[str, ...]: ...

    async def revalidate_seeds(
        self,
        profile: PlanningProfile,
    ) -> tuple[str, ...]: ...


class PipelineAiGateway:
    """Real implementation calling pure `savora_ai` pipelines via `asyncio.to_thread`."""

    def __init__(self, runtime: AiRuntime) -> None:
        self._runtime = runtime

    @property
    def bundle(self) -> CatalogueBundle:
        return self._runtime.bundle

    async def craving(
        self,
        request: CravingRequest,
        profile: PlanningProfile,
        *,
        top_k: int = 10,
    ) -> CravingRecommendation:
        return await asyncio.to_thread(
            recommend_for_craving,
            request,
            profile,
            self._runtime.bundle,
            scorer=self._runtime.scorer,
            top_k=top_k,
        )

    async def plan_week(
        self,
        profile: PlanningProfile,
        *,
        week_id: str,
        start_date: date,
    ) -> WeekPlan:
        return await asyncio.to_thread(
            plan_week,
            profile,
            self._runtime.bundle,
            week_id=week_id,
            start_date=start_date,
            scorer=self._runtime.scorer,
        )

    async def substitute(
        self,
        profile: PlanningProfile,
        *,
        current: Mapping[str, str],
        slot: str,
        week_id: str,
        start_date: date,
        exclude_combination_ids: Iterable[str] = (),
        replacement_combination_id: str | None = None,
        preference: CravingRequest | None = None,
    ) -> WeekPlan:
        return await asyncio.to_thread(
            substitute_slot,
            profile,
            self._runtime.bundle,
            current=current,
            slot=slot,
            week_id=week_id,
            start_date=start_date,
            exclude_combination_ids=tuple(exclude_combination_ids),
            replacement_combination_id=replacement_combination_id,
            preference=preference,
            scorer=self._runtime.scorer,
        )

    async def replacements(
        self,
        profile: PlanningProfile,
        *,
        current: Mapping[str, str],
        slot: str,
        preference: CravingRequest | None = None,
        exclude_combination_ids: Iterable[str] = (),
        limit: int = 6,
    ) -> ReplacementOptions:
        return await asyncio.to_thread(
            suggest_replacements,
            profile,
            self._runtime.bundle,
            current=current,
            slot=slot,
            preference=preference,
            exclude_combination_ids=tuple(exclude_combination_ids),
            scorer=self._runtime.scorer,
            limit=limit,
        )

    async def seeds(
        self,
        profile: PlanningProfile,
        *,
        limit: int = DEFAULT_SUGGESTIONS,
    ) -> SeedSuggestions:
        return await asyncio.to_thread(
            suggest_seeds,
            profile,
            self._runtime.bundle,
            limit=limit,
        )

    async def confirm_seeds(
        self,
        profile: PlanningProfile,
        picks: Sequence[str],
    ) -> tuple[str, ...]:
        return await asyncio.to_thread(
            confirm_seeds,
            profile,
            self._runtime.bundle,
            list(picks),
        )

    async def revalidate_seeds(
        self,
        profile: PlanningProfile,
    ) -> tuple[str, ...]:
        return await asyncio.to_thread(
            revalidate_seeds,
            profile,
            self._runtime.bundle,
        )


def get_ai_gateway(
    runtime: Annotated[AiRuntime, Depends(get_ai_runtime)],
) -> AiGateway:
    return PipelineAiGateway(runtime)


def get_craving_parser(
    runtime: Annotated[AiRuntime, Depends(get_ai_runtime)],
) -> CravingParser:
    """The NLU parser built once at startup (local Qwen + template, or template only)."""
    return runtime.parser
