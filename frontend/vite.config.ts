import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    host: true,
    allowedHosts: true,
    // Dev-only: forward portal API calls to the backend process. The origin
    // override lets the backend's same-origin check accept requests that the
    // browser sent from this dev preview's own origin (e.g. an e2b preview host).
    proxy: Object.fromEntries(
      ["/api", "/auth", "/health"].map((path) => [
        path,
        {
          target: process.env.VITE_API_TARGET ?? "http://127.0.0.1:8080",
          headers: { origin: process.env.PORTAL_PUBLIC_ORIGIN ?? "http://127.0.0.1:8080" },
        },
      ]),
    ),
  },
  test: { environment: "jsdom", setupFiles: "./src/test/setup.ts" },
});
