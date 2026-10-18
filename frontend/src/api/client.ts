import createClient from "openapi-fetch";

import type { paths } from "./schema";

interface ClientOptions {
  // Empty by default: the API is same-origin in development (Vite proxy) and production (nginx).
  baseUrl?: string;
  fetch?: typeof fetch;
}

export function createApiClient({ baseUrl = "", fetch = globalThis.fetch }: ClientOptions = {}) {
  return createClient<paths>({ baseUrl, fetch });
}

export const api = createApiClient();

export async function fetchHealth(client = api) {
  const { data, error } = await client.GET("/api/health");
  if (error || !data) throw new Error("API health check failed");
  return data;
}
