import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { hasSession, setSession } from "@/lib/api-request";
import {
  forgotPasswordApi,
  getMeApi,
  loginApi,
  logoutApi,
  registerApi,
  resetPasswordApi,
  type ForgotPasswordRequest,
  type LoginRequest,
  type RegisterRequest,
  type ResetPasswordRequest,
} from "./auth.api";

export const authKeys = {
  me: ["auth", "me"] as const,
};

export function useCurrentUserQuery(enabled = true) {
  return useQuery({
    queryKey: authKeys.me,
    queryFn: getMeApi,
    enabled: enabled && hasSession(),
    retry: false,
  });
}

export function useLoginMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LoginRequest) => loginApi(payload),
    onSuccess: (data) => {
      setSession(true);
      queryClient.setQueryData(authKeys.me, data.user);
    },
  });
}

/** Ends the session (the server clears the cookie) and every cached user query; the
 * caller navigates away. Local state is cleared even when the server is unreachable. */
export function useLogout() {
  const queryClient = useQueryClient();
  return () => {
    setSession(false);
    queryClient.clear();
    void logoutApi().catch(() => undefined);
  };
}

export function useRegisterMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RegisterRequest) => registerApi(payload),
    onSuccess: (data) => {
      setSession(true);
      queryClient.setQueryData(authKeys.me, data.user);
    },
  });
}

export function useForgotPasswordMutation() {
  return useMutation({ mutationFn: (payload: ForgotPasswordRequest) => forgotPasswordApi(payload) });
}

export function useResetPasswordMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ResetPasswordRequest) => resetPasswordApi(payload),
    onSuccess: () => {
      // The server ended every earlier session; drop what this browser kept of it.
      setSession(false);
      queryClient.clear();
    },
  });
}
