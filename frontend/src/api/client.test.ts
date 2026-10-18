import { describe, expect, it } from "vitest";

import { ApiError, createApiClient, fetchHealth, planTrip, searchPlaces } from "./client";

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

function respond(status: number, body: string, type = "application/json"): typeof fetch {
  return async () => new Response(body, { status, headers: { "Content-Type": type } });
}

const PLACE = { label: "Denver, CO, USA", lat: 39.74, lon: -104.99 };
const TRIP = {
  origin: PLACE,
  destination: { label: "Boulder, CO, USA", lat: 40.01, lon: -105.27 },
  departure: "2026-10-19T14:00:00-06:00",
  load_lb: 30_000,
  interval_mi: 25 as const,
};

describe("API errors (plan-api D5)", () => {
  it("carry the API's own message and status", async () => {
    const client = createApiClient({
      baseUrl: "http://api.test",
      fetch: respond(422, JSON.stringify({ detail: "No truck route found between these places." })),
    });
    const error = await planTrip(TRIP, undefined, client).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 422, message: "No truck route found between these places." });
  });

  it("explain a gateway page without showing its HTML", async () => {
    const client = createApiClient({
      baseUrl: "http://api.test",
      fetch: respond(502, "<html>Bad Gateway</html>", "text/html"),
    });
    await expect(searchPlaces("Denv", undefined, client)).rejects.toThrow(
      "The server is having trouble. Try again in a minute.",
    );
  });

  it("explain a network failure", async () => {
    const client = createApiClient({
      baseUrl: "http://api.test",
      fetch: async () => {
        throw new TypeError("Failed to fetch");
      },
    });
    await expect(searchPlaces("Denv", undefined, client)).rejects.toMatchObject({
      status: 0,
      message: "Can't reach the server. Check your connection and try again.",
    });
  });

  it("let an aborted search stay an abort", async () => {
    const client = createApiClient({
      baseUrl: "http://api.test",
      fetch: async () => {
        throw new DOMException("aborted", "AbortError");
      },
    });
    await expect(searchPlaces("Denv", undefined, client)).rejects.toMatchObject({
      name: "AbortError",
    });
  });
});

describe("searchPlaces", () => {
  it("returns the API's places", async () => {
    const client = createApiClient({
      baseUrl: "http://api.test",
      fetch: respond(200, JSON.stringify([PLACE])),
    });
    await expect(searchPlaces("Denv", undefined, client)).resolves.toEqual([PLACE]);
  });
});
