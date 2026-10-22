import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getStoredToken } from "@/lib/api-request";
import {
  getCuisinesApi,
  getProfileApi,
  getSeedSuggestionsApi,
  putSeedPicksApi,
  searchCatalogueDishesApi,
  upsertProfileApi,
  type ProfileUpsertRequest,
  type SeedPicksRequest,
} from "./profile.api";

export const profileKeys = {
  profile: ["profile"] as const,
  cuisines: ["catalogue", "cuisines"] as const,
  seedSuggestions: ["onboarding", "seed-suggestions"] as const,
  dishSearch: (q: string) => ["catalogue", "dishes", q] as const,
};

export function useProfileQuery(enabled = true) {
  return useQuery({
    queryKey: profileKeys.profile,
    queryFn: getProfileApi,
    enabled: enabled && Boolean(getStoredToken()),
    retry: false,
  });
}

export function useCuisinesQuery() {
  return useQuery({
    queryKey: profileKeys.cuisines,
    queryFn: getCuisinesApi,
    enabled: Boolean(getStoredToken()),
  });
}

export function useUpsertProfileMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProfileUpsertRequest) => upsertProfileApi(payload),
    onSuccess: (data) => {
      queryClient.setQueryData(profileKeys.profile, data);
      queryClient.invalidateQueries({ queryKey: profileKeys.seedSuggestions });
    },
  });
}

export function useSeedSuggestionsQuery(enabled = true) {
  return useQuery({
    queryKey: profileKeys.seedSuggestions,
    queryFn: getSeedSuggestionsApi,
    enabled: enabled && Boolean(getStoredToken()),
  });
}

export function useConfirmSeedPicksMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SeedPicksRequest) => putSeedPicksApi(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: profileKeys.profile });
    },
  });
}

export function useDishSearchQuery(q: string) {
  return useQuery({
    queryKey: profileKeys.dishSearch(q),
    queryFn: () => searchCatalogueDishesApi(q),
    enabled: Boolean(getStoredToken()) && q.trim().length > 0,
  });
}
