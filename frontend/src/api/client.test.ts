import { describe, expect, it } from "vitest";

import { createApiClient, fetchHealth } from "./client";

function stubFetch(status: number, body: unknown): typeof fetch {
  return async (input) => {
    const url = input instanceof Request ? input.url : String(input);
    expect(new URL(url).pathname).toBe("/api/health");
    return new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  };
}

describe("fetchHealth", () => {
  it("returns the API status and build version", async () => {
    const client = createApiClient({
      baseUrl: "http://api.test",
      fetch: stubFetch(200, { status: "ok", version: "abc1234" }),
    });

    await expect(fetchHealth(client)).resolves.toEqual({ status: "ok", version: "abc1234" });
  });

  it("throws when the API answers with an error", async () => {
    const client = createApiClient({
      baseUrl: "http://api.test",
      fetch: stubFetch(503, { detail: "down" }),
    });

    await expect(fetchHealth(client)).rejects.toThrow("API health check failed");
  });
});
