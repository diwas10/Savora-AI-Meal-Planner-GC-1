import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  cancelMealPlanApi,
  createMealPlanApi,
  createSubstitutionApi,
  getMealPlanApi,
  getReplacementOptionsApi,
  getSubstitutionApi,
  listMealPlansApi,
  type CreateSubstitutionRequest,
  type GeneratePlanRequest,
  type MealPlanSummaryDto,
  type ReplacementOptionsRequest,
} from "./meal-planning.api";

export const mealPlanKeys = {
  all: ["meal-plans"] as const,
  list: () => ["meal-plans", "list"] as const,
  detail: (planId: string) => ["meal-plans", "detail", planId] as const,
  substitution: (subId: string) => ["substitutions", subId] as const,
};

const POLL_MS = 2500;

/** Every saved plan, newest first; polls while one is still being prepared. */
export function useMealPlansQuery() {
  return useQuery({
    queryKey: mealPlanKeys.list(),
    queryFn: () => listMealPlansApi(false),
    refetchInterval: (query) =>
      query.state.data?.some((p) => p.status === "GENERATING") ? POLL_MS : false,
  });
}

/** The current (ready) plan and the newest job, derived from the list. */
export function selectPlans(plans: MealPlanSummaryDto[] | undefined) {
  const list = plans ?? [];
  return {
    current: list.find((p) => p.isCurrent) ?? null,
    latest: list[0] ?? null,
    generating: list.find((p) => p.status === "GENERATING") ?? null,
  };
}

export function useMealPlanDetailQuery(planId: string | null | undefined) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: mealPlanKeys.detail(planId ?? ""),
    queryFn: async () => {
      const data = await getMealPlanApi(planId as string);
      // Once a plan completes or settles, make sure the plan list query is synchronized.
      if (data.status !== "GENERATING") {
        void queryClient.invalidateQueries({ queryKey: mealPlanKeys.list() });
      }
      return data;
    },
    enabled: Boolean(planId),
    // Stale immediately while GENERATING so polling/navigation always gets freshest status.
    staleTime: (query) => (query.state.data?.status === "GENERATING" ? 0 : 60_000),
    // Switching plans (e.g. to the revision a swap just created) keeps the current plan
    // on screen until the next one loads: no skeleton flash, open sheets stay mounted.
    placeholderData: keepPreviousData,
    refetchInterval: (query) => (query.state.data?.status === "GENERATING" ? POLL_MS : false),
  });
}

export function useCreateMealPlanMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: GeneratePlanRequest) => createMealPlanApi(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: mealPlanKeys.all }),
  });
}

export function useCancelMealPlanMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (planId: string) => cancelMealPlanApi(planId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: mealPlanKeys.all }),
  });
}

export function useReplacementOptionsMutation(planId: string, slotId: string) {
  return useMutation({
    mutationFn: (payload: ReplacementOptionsRequest) =>
      getReplacementOptionsApi(planId, slotId, payload),
  });
}

export function useCreateSubstitutionMutation(planId: string) {
  return useMutation({
    mutationFn: (payload: CreateSubstitutionRequest) => createSubstitutionApi(planId, payload),
  });
}

/** Polls a swap until it settles, then refreshes the plans (a new revision may exist). */
export function useSubstitutionQuery(substitutionId: string | null) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: mealPlanKeys.substitution(substitutionId ?? ""),
    queryFn: async () => {
      const sub = await getSubstitutionApi(substitutionId as string);
      if (sub.status !== "GENERATING") {
        await queryClient.invalidateQueries({ queryKey: mealPlanKeys.all });
      }
      return sub;
    },
    enabled: Boolean(substitutionId),
    refetchInterval: (query) => (query.state.data?.status === "GENERATING" ? 2000 : false),
  });
}
