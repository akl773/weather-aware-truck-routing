import { type Page, type Request, expect, test } from "@playwright/test";

import corridor from "./fixtures/corridor-denver-colorado-springs.json" with { type: "json" };
import coloradoSprings from "./fixtures/places-colorado-springs.json" with { type: "json" };
import denver from "./fixtures/places-denver.json" with { type: "json" };
import plan from "./fixtures/plan-denver-colorado-springs.json" with { type: "json" };

// The API answers from responses recorded off our own API, so the test needs no keys and spends
// no provider budget; the backend's own tests cover how those answers are made.
async function serveApi(page: Page) {
  const calls: Request[] = [];
  // By path: a glob like **/api/** would also catch the dev server's /src/api/ modules.
  await page.route((url) => url.pathname.startsWith("/api/"), async (route) => {
    const request = route.request();
    calls.push(request);
    const url = new URL(request.url());
    if (url.pathname === "/api/health") return route.fulfill({ json: { status: "ok", version: "e2e" } });
    if (url.pathname === "/api/places") {
      const q = (url.searchParams.get("q") ?? "").toLowerCase();
      return route.fulfill({ json: q.startsWith("den") ? denver : coloradoSprings });
    }
    if (url.pathname === "/api/plan") return route.fulfill({ json: plan });
    if (url.pathname === "/api/corridor") return route.fulfill({ json: corridor });
    return route.fulfill({ status: 404, json: { detail: "Not mocked." } });
  });
  // A blank basemap with the label layer the heatmap draws beneath; no tiles are fetched.
  await page.route("https://tiles.openfreemap.org/**", (route) =>
    route.request().url().endsWith("/styles/positron")
      ? route.fulfill({
          json: {
            version: 8,
            sources: {},
            layers: [
              { id: "background", type: "background", paint: { "background-color": "#eef0f2" } },
              { id: "waterway_line_label", type: "background", paint: { "background-opacity": 0 } },
            ],
          },
        })
      : route.abort(),
  );
  return calls;
}

async function pickPlace(page: Page, id: string, typed: string, label: string) {
  await page.locator(`#${id}`).fill(typed);
  await page.getByRole("option", { name: label, exact: true }).click();
  await expect(page.locator(`#${id}`)).toHaveValue(label);
}

test("plans a trip, compares three routes and scrubs 48 hours without a request", async ({
  page,
}) => {
  const calls = await serveApi(page);
  await page.goto("/");

  await pickPlace(page, "origin", "Denver", "Denver, CO, USA");
  await pickPlace(page, "destination", "Colorado Springs", "Colorado Springs, CO, USA");
  await page.getByLabel("Load").fill("30000");
  await page.getByRole("button", { name: "10 mi" }).click();
  await page.getByRole("button", { name: "Plan routes" }).click();

  const sent = calls.find((call) => call.url().endsWith("/api/plan"))?.postDataJSON();
  expect(sent).toMatchObject({ load_lb: 30000, interval_mi: 10 });
  expect(sent.departure).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:00:00-0[67]:00$/);

  // The recommendation, then the three routes best first, the recommended one selected.
  await expect(page.getByText(`Recommended: Route ${plan.recommendation.route_id}`)).toBeVisible();
  await expect(page.getByText(plan.recommendation.reason)).toBeVisible();
  const cards = page.getByRole("region", { name: "Routes, best first" }).getByRole("button");
  await expect(cards).toHaveCount(3);
  for (const [i, id] of plan.recommendation.ranking.entries()) {
    await expect(cards.nth(i)).toHaveAccessibleName(`Route ${id}, ranked ${i + 1}`);
  }
  await expect(cards.first()).toHaveAttribute("aria-pressed", "true");

  // Choosing another route moves the selection.
  await cards.nth(1).click();
  await expect(cards.nth(1)).toHaveAttribute("aria-pressed", "true");
  await expect(cards.first()).toHaveAttribute("aria-pressed", "false");

  // The corridor has loaded once its legend replaces the loading line.
  const timeline = page.getByRole("region", { name: "Forecast timeline" });
  await expect(timeline.getByText("No Travel")).toBeVisible();
  const requestsBeforeScrub = calls.length;

  const slider = timeline.getByRole("slider", { name: "Hours after departure" });
  await slider.focus();
  await page.keyboard.press("End");
  await expect(slider).toHaveAttribute("aria-valuenow", "48");
  await expect(timeline.getByText("48 h after departure")).toBeVisible();
  await page.keyboard.press("Home");
  await page.keyboard.press("PageUp");
  await expect(slider).toHaveAttribute("aria-valuenow", "3");
  await page.keyboard.press("ArrowRight");
  await expect(slider).toHaveAttribute("aria-valuenow", "3.25");

  await timeline.getByRole("button", { name: "Wind" }).click();
  await expect(timeline.getByText("mph")).toBeVisible();

  await timeline.getByRole("button", { name: "Play" }).click();
  await expect
    .poll(async () => Number(await slider.getAttribute("aria-valuenow")))
    .toBeGreaterThan(5);
  await timeline.getByRole("button", { name: "Pause" }).click();

  // Scrubbing, switching views and Play never touch the network (corridor-heatmap D7).
  expect(calls.length).toBe(requestsBeforeScrub);
});
