import { defineConfig, devices } from "@playwright/test";

const PORT = 4300;

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/test-results",
  reporter: [["list"], ["html", { outputFolder: "e2e/playwright-report", open: "never" }]],
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: `http://localhost:${PORT}`,
    // ETAs and slider times are shown in the browser's zone (ui D3); pin it so runs agree.
    timezoneId: "America/Denver",
    locale: "en-US",
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 900 },
        // CI runners have no GPU; the map needs WebGL from the software renderer.
        launchOptions: { args: ["--enable-unsafe-swiftshader"] },
      },
    },
  ],
  webServer: {
    command: `npx vite --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
