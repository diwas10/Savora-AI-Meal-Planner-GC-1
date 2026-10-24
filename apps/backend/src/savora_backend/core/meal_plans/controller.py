"""Weekly plan routes, including the swap flow's options and start."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from savora_ai.core.craving_nlu import CravingParser
from savora_ai.core.pipelines.planning import SLOT_ID
from savora_backend.ai.gateway import AiGateway, get_ai_gateway, get_craving_parser
from savora_backend.auth import CurrentUser
from savora_backend.core.meal_plans.dependencies import get_job_session_factory
from savora_backend.core.meal_plans.dto import (
    CreateSubstitutionAcceptedDto,
    CreateSubstitutionRequest,
    GeneratePlanAcceptedDto,
    GeneratePlanRequest,
    MealPlanDetailDto,
    MealPlanSummaryDto,
    ReplacementOptionsDto,
    ReplacementOptionsRequest,
)
from savora_backend.core.meal_plans.jobs import SessionFactory
from savora_backend.core.meal_plans.service import MealPlanService
from savora_backend.core.substitutions.service import SubstitutionService
from savora_backend.database import get_session
from savora_backend.decorators import response_message
from savora_backend.interceptors import TransformRoute

meal_plans_router = APIRouter(prefix="/meal-plans", tags=["meal-plans"], route_class=TransformRoute)

SessionDep = Annotated[AsyncSession, Depends(get_session)]
GatewayDep = Annotated[AiGateway, Depends(get_ai_gateway)]
ParserDep = Annotated[CravingParser, Depends(get_craving_parser)]
JobFactoryDep = Annotated[SessionFactory, Depends(get_job_session_factory)]
SlotPath = Annotated[str, Path(pattern=SLOT_ID)]


@meal_plans_router.post("", status_code=status.HTTP_202_ACCEPTED)
@response_message("Meal plan generation started")
async def create_meal_plan(
    body: GeneratePlanRequest,
    user: CurrentUser,
    session: SessionDep,
    gateway: GatewayDep,
    job_factory: JobFactoryDep,
) -> GeneratePlanAcceptedDto:
    return await MealPlanService(session, gateway, job_factory).start_generation(user.id, body)


@meal_plans_router.get("")
@response_message("Meal plans retrieved")
async def list_meal_plans(
    user: CurrentUser,
    session: SessionDep,
    gateway: GatewayDep,
    current: bool = Query(default=False),
) -> list[MealPlanSummaryDto]:
    return await MealPlanService(session, gateway).list_plans(user.id, current_only=current)


@meal_plans_router.get("/{plan_id}")
@response_message("Meal plan retrieved")
async def get_meal_plan(
    plan_id: UUID, user: CurrentUser, session: SessionDep, gateway: GatewayDep
) -> MealPlanDetailDto:
    return await MealPlanService(session, gateway).get_plan(user.id, plan_id)


@meal_plans_router.post("/{plan_id}/cancel")
@response_message("Meal plan generation cancelled")
async def cancel_meal_plan(
    plan_id: UUID,
    user: CurrentUser,
    session: SessionDep,
    gateway: GatewayDep,
) -> MealPlanDetailDto:
    return await MealPlanService(session, gateway).cancel_plan(user.id, plan_id)


@meal_plans_router.post("/{plan_id}/slots/{slot_id}/replacement-options")
@response_message("Replacement options ranked")
async def list_replacement_options(
    plan_id: UUID,
    slot_id: SlotPath,
    body: ReplacementOptionsRequest,
    user: CurrentUser,
    session: SessionDep,
    gateway: GatewayDep,
    parser: ParserDep,
) -> ReplacementOptionsDto:
    service = SubstitutionService(session, gateway, parser)
    return await service.replacement_options(user.id, plan_id, slot_id, body)


@meal_plans_router.post("/{plan_id}/substitutions", status_code=status.HTTP_202_ACCEPTED)
@response_message("Meal plan substitution started")
async def create_meal_plan_substitution(
    plan_id: UUID,
    body: CreateSubstitutionRequest,
    user: CurrentUser,
    session: SessionDep,
    gateway: GatewayDep,
    parser: ParserDep,
    job_factory: JobFactoryDep,
) -> CreateSubstitutionAcceptedDto:
    service = SubstitutionService(session, gateway, parser, job_factory)
    return await service.start_substitution(user.id, plan_id, body)
