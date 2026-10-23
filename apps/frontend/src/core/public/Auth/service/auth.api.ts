import type { Schema } from "@savora/contracts";
import { apiRequest } from "@/lib/api-request";

export type AuthResponse = Schema<"AuthResponse">;
export type LoginRequest = Schema<"LoginRequest">;
export type RegisterRequest = Schema<"RegisterRequest">;
export type UserDto = Schema<"UserDto">;
export type ForgotPasswordRequest = Schema<"ForgotPasswordRequest">;
export type ResetPasswordRequest = Schema<"ResetPasswordRequest">;

export async function loginApi(payload: LoginRequest): Promise<AuthResponse> {
  return apiRequest<AuthResponse>({
    method: "POST",
    url: "/auth/login",
    data: payload,
  });
}

export async function registerApi(payload: RegisterRequest): Promise<AuthResponse> {
  return apiRequest<AuthResponse>({
    method: "POST",
    url: "/auth/register",
    data: payload,
  });
}

export async function getMeApi(): Promise<UserDto> {
  return apiRequest<UserDto>({
    method: "GET",
    url: "/auth/me",
  });
}

export async function logoutApi(): Promise<void> {
  await apiRequest<null>({ method: "POST", url: "/auth/logout" });
}

export async function forgotPasswordApi(payload: ForgotPasswordRequest): Promise<void> {
  await apiRequest<null>({ method: "POST", url: "/auth/forgot-password", data: payload });
}

export async function resetPasswordApi(payload: ResetPasswordRequest): Promise<void> {
  await apiRequest<null>({ method: "POST", url: "/auth/reset-password", data: payload });
}
