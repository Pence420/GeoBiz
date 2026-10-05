import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            {
              name: "geospatial-vendor",
              test: /node_modules[\\/](maplibre-gl|pmtiles)[\\/]/,
              priority: 20,
            },
            {
              name: "react-vendor",
              test: /node_modules[\\/](react|react-dom)[\\/]/,
              priority: 10,
            },
          ],
        },
      },
    },
  },
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
