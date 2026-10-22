import type { Schema } from "@savora/contracts";
import { apiRequest } from "@/lib/api-request";

export type GeneratePlanRequest = Schema<"GeneratePlanRequest">;
export type GeneratePlanAcceptedDto = Schema<"GeneratePlanAcceptedDto">;
export type MealPlanSummaryDto = Schema<"MealPlanSummaryDto">;
export type MealPlanDetailDto = Schema<"MealPlanDetailDto">;
export type CreateSubstitutionRequest = Schema<"CreateSubstitutionRequest">;
export type CreateSubstitutionAcceptedDto = Schema<"CreateSubstitutionAcceptedDto">;
export type SubstitutionDetailDto = Schema<"SubstitutionDetailDto">;

export async function createMealPlanApi(
  payload: GeneratePlanRequest,
): Promise<GeneratePlanAcceptedDto> {
  return apiRequest<GeneratePlanAcceptedDto>({
    method: "POST",
    url: "/meal-plans",
    data: payload,
  });
}

export async function listMealPlansApi(
  current = false,
): Promise<MealPlanSummaryDto[]> {
  return apiRequest<MealPlanSummaryDto[]>({
    method: "GET",
    url: "/meal-plans",
    params: { current },
  });
}

export async function getMealPlanApi(planId: string): Promise<MealPlanDetailDto> {
  return apiRequest<MealPlanDetailDto>({
    method: "GET",
    url: `/meal-plans/${planId}`,
  });
}

export async function createSubstitutionApi(
  planId: string,
  payload: CreateSubstitutionRequest,
): Promise<CreateSubstitutionAcceptedDto> {
  return apiRequest<CreateSubstitutionAcceptedDto>({
    method: "POST",
    url: `/meal-plans/${planId}/substitutions`,
    data: payload,
  });
}

export async function getSubstitutionApi(
  substitutionId: string,
): Promise<SubstitutionDetailDto> {
  return apiRequest<SubstitutionDetailDto>({
    method: "GET",
    url: `/substitutions/${substitutionId}`,
  });
}
