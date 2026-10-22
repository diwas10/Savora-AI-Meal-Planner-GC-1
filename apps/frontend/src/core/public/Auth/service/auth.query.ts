import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getStoredToken, setStoredToken } from "@/lib/api-request";
import {
  getMeApi,
  loginApi,
  registerApi,
  type LoginRequest,
  type RegisterRequest,
} from "./auth.api";

export const authKeys = {
  me: ["auth", "me"] as const,
};

export function useCurrentUserQuery(enabled = true) {
  return useQuery({
    queryKey: authKeys.me,
    queryFn: getMeApi,
    enabled: enabled && Boolean(getStoredToken()),
    retry: false,
  });
}

export function useLoginMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LoginRequest) => loginApi(payload),
    onSuccess: (data) => {
      setStoredToken(data.accessToken);
      queryClient.setQueryData(authKeys.me, data.user);
    },
  });
}

/** Clears the token and every cached user query, then the caller navigates away. */
export function useLogout() {
  const queryClient = useQueryClient();
  return () => {
    setStoredToken(null);
    queryClient.clear();
  };
}

export function useRegisterMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RegisterRequest) => registerApi(payload),
    onSuccess: (data) => {
      setStoredToken(data.accessToken);
      queryClient.setQueryData(authKeys.me, data.user);
    },
  });
}
