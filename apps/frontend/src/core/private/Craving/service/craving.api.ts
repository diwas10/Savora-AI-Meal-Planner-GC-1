import type { Schema } from "@savora/contracts";
import { apiRequest } from "@/lib/api-request";

export type CravingTextRequest = Schema<"CravingTextRequest">;
export type CravingRecommendationsResponse = Schema<"CravingRecommendationsResponse">;
export type CravingSwapSuggestedResponse = Schema<"CravingSwapSuggestedResponse">;
export type CravingResponse =
  | CravingRecommendationsResponse
  | CravingSwapSuggestedResponse;

export async function postCravingApi(
  payload: CravingTextRequest,
): Promise<CravingResponse> {
  return apiRequest<CravingResponse>({
    method: "POST",
    url: "/cravings",
    data: payload,
  });
}
