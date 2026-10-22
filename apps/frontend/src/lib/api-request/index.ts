import axios, { AxiosError, type AxiosRequestConfig } from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_STORAGE_KEY = "savora_access_token";
/** localStorage key of the persisted query cache (cleared on logout). */
export const QUERY_CACHE_KEY = "savora_query_cache";

export interface SuccessEnvelope<T> {
  success: true;
  source: string;
  data: T;
  message: string;
  status: number;
}

export interface ErrorEnvelope {
  success: false;
  source: string;
  message: string;
  status: number;
  description?: Record<string, string[]>;
}

export class ApiError extends Error {
  readonly status: number;
  readonly source: string;
  readonly fieldErrors: Record<string, string[]>;

  constructor(
    message: string,
    status: number,
    source = "api",
    fieldErrors: Record<string, string[]> = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.source = source;
    this.fieldErrors = fieldErrors;
  }
}

export function getStoredToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token: string | null): void {
  if (typeof window === "undefined") {
    return;
  }
  if (token === null) {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    window.localStorage.removeItem(QUERY_CACHE_KEY);
  } else {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  }
}

const axiosInstance = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  headers: {
    "Content-Type": "application/json",
  },
});

axiosInstance.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) {
    return error;
  }
  if (error instanceof AxiosError) {
    const status = error.response?.status ?? 500;
    const data = error.response?.data as Partial<ErrorEnvelope> | undefined;
    if (data && typeof data.message === "string") {
      return new ApiError(
        data.message,
        data.status ?? status,
        data.source ?? "api",
        data.description ?? {},
      );
    }
    if (!error.response) {
      // No response at all: offline or the server is unreachable (status 0).
      return new ApiError("Can't reach Savora. Check your connection and try again.", 0);
    }
    return new ApiError(error.message || "Network request failed", status);
  }
  if (error instanceof Error) {
    return new ApiError(error.message, 500);
  }
  return new ApiError("Unexpected error", 500);
}

export async function apiRequest<T>(config: AxiosRequestConfig): Promise<T> {
  try {
    const response = await axiosInstance.request<SuccessEnvelope<T>>(config);
    const body = response.data;
    if (body && typeof body === "object" && "data" in body) {
      return body.data;
    }
    return body as unknown as T;
  } catch (error: unknown) {
    throw toApiError(error);
  }
}
