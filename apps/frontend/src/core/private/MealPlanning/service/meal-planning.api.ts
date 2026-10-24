import type { Schema } from "@savora/contracts";
import { apiRequest } from "@/lib/api-request";

export type GeneratePlanRequest = Schema<"GeneratePlanRequest">;
export type GeneratePlanAcceptedDto = Schema<"GeneratePlanAcceptedDto">;
export type MealPlanSummaryDto = Schema<"MealPlanSummaryDto">;
export type MealPlanDetailDto = Schema<"MealPlanDetailDto">;
export type MealPlanSlotDto = Schema<"MealPlanSlotDto">;
export type PlannedMeal = Schema<"PlannedMeal">;
export type MealPlanJobStatus = Schema<"MealPlanJobStatus">;
export type ReplacementOptionsRequest = Schema<"ReplacementOptionsRequest">;
export type ReplacementOptionsDto = Schema<"ReplacementOptionsDto">;
export type ReplacementOption = Schema<"ReplacementOption">;
export type CreateSubstitutionRequest = Schema<"CreateSubstitutionRequest">;
export type CreateSubstitutionAcceptedDto = Schema<"CreateSubstitutionAcceptedDto">;
export type SubstitutionDetailDto = Schema<"SubstitutionDetailDto">;

export function createMealPlanApi(payload: GeneratePlanRequest): Promise<GeneratePlanAcceptedDto> {
  return apiRequest({ method: "POST", url: "/meal-plans", data: payload });
}

export function listMealPlansApi(current = false): Promise<MealPlanSummaryDto[]> {
  return apiRequest({ method: "GET", url: "/meal-plans", params: { current } });
}

export function getMealPlanApi(planId: string): Promise<MealPlanDetailDto> {
  return apiRequest({ method: "GET", url: `/meal-plans/${planId}` });
}

export function cancelMealPlanApi(planId: string): Promise<MealPlanDetailDto> {
  return apiRequest({ method: "POST", url: `/meal-plans/${planId}/cancel` });
}

export function getReplacementOptionsApi(
  planId: string,
  slotId: string,
  payload: ReplacementOptionsRequest,
): Promise<ReplacementOptionsDto> {
  return apiRequest({
    method: "POST",
    url: `/meal-plans/${planId}/slots/${slotId}/replacement-options`,
    data: payload,
  });
}

export function createSubstitutionApi(
  planId: string,
  payload: CreateSubstitutionRequest,
): Promise<CreateSubstitutionAcceptedDto> {
  return apiRequest({ method: "POST", url: `/meal-plans/${planId}/substitutions`, data: payload });
}

export function getSubstitutionApi(substitutionId: string): Promise<SubstitutionDetailDto> {
  return apiRequest({ method: "GET", url: `/substitutions/${substitutionId}` });
}
