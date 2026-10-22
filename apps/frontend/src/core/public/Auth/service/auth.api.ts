import type { Schema } from "@savora/contracts";
import { apiRequest } from "@/lib/api-request";

export type AuthResponse = Schema<"AuthResponse">;
export type LoginRequest = Schema<"LoginRequest">;
export type RegisterRequest = Schema<"RegisterRequest">;
export type UserDto = Schema<"UserDto">;

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
