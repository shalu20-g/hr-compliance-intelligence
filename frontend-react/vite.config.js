import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Backend base URL can be overridden with VITE_API_URL.
// The dev server proxies /api to the FastAPI backend for local development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_URL || "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
