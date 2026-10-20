import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getStoredToken } from "@/lib/api-request";
import {
  createMealPlanApi,
  createSubstitutionApi,
  getMealPlanApi,
  getSubstitutionApi,
  listMealPlansApi,
  type CreateSubstitutionRequest,
  type GeneratePlanRequest,
} from "./meal-planning.api";

export const mealPlanKeys = {
  list: (current: boolean) => ["meal-plans", "list", { current }] as const,
  detail: (planId: string) => ["meal-plans", "detail", planId] as const,
  substitution: (subId: string) => ["substitutions", subId] as const,
};

export function useMealPlansListQuery(current = false) {
  return useQuery({
    queryKey: mealPlanKeys.list(current),
    queryFn: () => listMealPlansApi(current),
    enabled: Boolean(getStoredToken()),
  });
}

export function useMealPlanDetailQuery(planId: string | null) {
  return useQuery({
    queryKey: mealPlanKeys.detail(planId ?? ""),
    queryFn: () => getMealPlanApi(planId!),
    enabled: Boolean(getStoredToken()) && Boolean(planId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "GENERATING" ? 2500 : false;
    },
  });
}

export function useCreateMealPlanMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: GeneratePlanRequest) => createMealPlanApi(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["meal-plans"] });
    },
  });
}

export function useCreateSubstitutionMutation(planId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateSubstitutionRequest) =>
      createSubstitutionApi(planId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["meal-plans"] });
    },
  });
}

export function useSubstitutionPollingQuery(substitutionId: string | null) {
  return useQuery({
    queryKey: mealPlanKeys.substitution(substitutionId ?? ""),
    queryFn: () => getSubstitutionApi(substitutionId!),
    enabled: Boolean(getStoredToken()) && Boolean(substitutionId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "GENERATING" ? 2000 : false;
    },
  });
}
