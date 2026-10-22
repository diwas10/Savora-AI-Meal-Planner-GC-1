import type { Schema } from "@savora/contracts";
import { ApiError, apiRequest } from "@/lib/api-request";

export type ProfileEnvelopeData = Schema<"ProfileEnvelopeData">;
export type ProfileUpsertRequest = Schema<"ProfileUpsertRequest">;
export type CuisineOptionDto = Schema<"CuisineOptionDto">;
export type SeedSuggestions = Schema<"SeedSuggestions">;
export type SeedPicksRequest = Schema<"SeedPicksRequest">;
export type SeedPicksResponse = Schema<"SeedPicksResponse">;
export type CatalogueDishDto = Schema<"CatalogueDishDto">;

/** The profile, or null when the user has not completed onboarding yet (404). */
export async function getProfileApi(): Promise<ProfileEnvelopeData | null> {
  try {
    return await apiRequest<ProfileEnvelopeData>({ method: "GET", url: "/profile" });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export async function upsertProfileApi(
  payload: ProfileUpsertRequest,
): Promise<ProfileEnvelopeData> {
  return apiRequest<ProfileEnvelopeData>({
    method: "PUT",
    url: "/profile",
    data: payload,
  });
}

export async function getCuisinesApi(): Promise<CuisineOptionDto[]> {
  return apiRequest<CuisineOptionDto[]>({
    method: "GET",
    url: "/catalogue/cuisines",
  });
}

export async function getSeedSuggestionsApi(): Promise<SeedSuggestions> {
  return apiRequest<SeedSuggestions>({
    method: "GET",
    url: "/onboarding/seed-suggestions",
  });
}

export async function putSeedPicksApi(
  payload: SeedPicksRequest,
): Promise<SeedPicksResponse> {
  return apiRequest<SeedPicksResponse>({
    method: "PUT",
    url: "/onboarding/seed-picks",
    data: payload,
  });
}

export async function searchCatalogueDishesApi(q: string): Promise<CatalogueDishDto[]> {
  return apiRequest<CatalogueDishDto[]>({
    method: "GET",
    url: "/catalogue/dishes",
    params: { q },
  });
}
