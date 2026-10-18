import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

export type Place = components["schemas"]["Place"];
export type PlanRequest = components["schemas"]["PlanRequest"];
export type PlanResponse = components["schemas"]["PlanResponse"];

interface ClientOptions {
  // Empty by default: the API is same-origin in development (Vite proxy) and production (nginx).
  baseUrl?: string;
  fetch?: typeof fetch;
}

export function createApiClient({ baseUrl = "", fetch = globalThis.fetch }: ClientOptions = {}) {
  return createClient<paths>({ baseUrl, fetch });
}

export type ApiClient = ReturnType<typeof createApiClient>;

export const api = createApiClient();

/** A failed API call, with the message the API wrote for the user (plan-api D5). */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const UNREACHABLE = "Can't reach the server. Check your connection and try again.";

function toApiError(body: unknown, response: Response): ApiError {
  const detail =
    typeof body === "object" && body !== null && "detail" in body ? body.detail : undefined;
  if (typeof detail === "string") return new ApiError(detail, response.status);
  // A proxy or gateway page rather than the API's own JSON.
  return new ApiError(
    response.status >= 500
      ? "The server is having trouble. Try again in a minute."
      : `The request failed (${response.status}).`,
    response.status,
  );
}

/** Runs a call, turning network failures and error responses into `ApiError`. */
async function call<T>(
  request: () => Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  let result;
  try {
    result = await request();
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(UNREACHABLE, 0);
  }
  if (result.data === undefined) throw toApiError(result.error, result.response);
  return result.data;
}

export async function fetchHealth(client = api) {
  const { data, error } = await client.GET("/api/health");
  if (error || !data) throw new Error("API health check failed");
  return data;
}

export function searchPlaces(q: string, signal?: AbortSignal, client: ApiClient = api) {
  return call(() => client.GET("/api/places", { params: { query: { q } }, signal }));
}

export function planTrip(body: PlanRequest, signal?: AbortSignal, client: ApiClient = api) {
  return call(() => client.POST("/api/plan", { body, signal }));
}
