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
  build: {
    // MapLibre alone is ~1.1 MB minified (296 KB gzipped) and ships as one module.
    chunkSizeWarningLimit: 1200,
    rolldownOptions: {
      output: {
        // Vendor code changes far less often than app code; separate chunks stay cached.
        codeSplitting: {
          groups: [
            { name: "deck", test: /node_modules[\\/]@(deck|luma|loaders|math)\.gl/ },
            { name: "mui", test: /node_modules[\\/]@(mui|emotion)/ },
            { name: "react", test: /node_modules[\\/](react|react-dom|scheduler)[\\/]/ },
          ],
        },
      },
    },
  },
  test: {
    environment: "node",
    // Set before any module loads, so formatters built at import time use it too.
    env: { TZ: "America/Denver" },
  },
});
