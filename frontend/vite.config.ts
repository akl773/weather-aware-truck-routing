/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Same-origin /api in development, as nginx provides in production.
    proxy: { "/api": process.env.API_PROXY_TARGET ?? "http://localhost:8000" },
  },
  test: {
    environment: "node",
  },
});
