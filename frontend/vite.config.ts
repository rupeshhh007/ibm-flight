/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The backend is local/demo-only. The dev server proxies API calls to it so the
// browser never needs a hardcoded backend address (bootstrap spec section 10).
const BACKEND = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": BACKEND,
      "/healthz": BACKEND,
      "/readyz": BACKEND,
    },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
