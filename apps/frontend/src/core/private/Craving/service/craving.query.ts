import { useMutation } from "@tanstack/react-query";
import { postCravingApi, type CravingTextRequest } from "./craving.api";

export function useCravingMutation() {
  return useMutation({
    mutationFn: (payload: CravingTextRequest) => postCravingApi(payload),
  });
}
