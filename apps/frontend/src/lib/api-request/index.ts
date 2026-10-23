import axios, { AxiosError, type AxiosRequestConfig } from "axios";

/** localStorage key of the "signed in" hint. The session itself is an httpOnly cookie
 * that no script can read; this flag only tells the UI whether to try authenticated
 * requests. */
const SESSION_HINT_KEY = "savora_signed_in";
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

export function hasSession(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return window.localStorage.getItem(SESSION_HINT_KEY) === "1";
}

export function setSession(signedIn: boolean): void {
  if (typeof window === "undefined") {
    return;
  }
  // Tokens from earlier builds lived in localStorage; never leave one behind.
  window.localStorage.removeItem("savora_access_token");
  if (signedIn) {
    window.localStorage.setItem(SESSION_HINT_KEY, "1");
  } else {
    window.localStorage.removeItem(SESSION_HINT_KEY);
    window.localStorage.removeItem(QUERY_CACHE_KEY);
  }
}

// Same origin: Next.js rewrites /api to FastAPI (next.config.ts), so the session cookie is
// first-party. The client header is required on cookie-authenticated writes (CSRF).
const axiosInstance = axios.create({
  baseURL: "/api",
  headers: {
    "Content-Type": "application/json",
    "X-Savora-Client": "web",
  },
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
