import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: ["frontend"],
    proxy: {
      "/api": { target: "http://backend:8000", changeOrigin: true },
      "/tiles": { target: "http://backend:8000", changeOrigin: true },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
