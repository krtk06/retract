import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY || "http://localhost:8000",
        changeOrigin: true,
      },
      // The eve agent's HTTP routes: sessions, streams, and approval replies.
      // Streamed responses need ws disabled so Vite proxies the SSE upgrade-free
      // fetch stream instead of buffering it.
      "/eve": {
        target: process.env.VITE_EVE_PROXY || "http://localhost:3000",
        changeOrigin: true,
        ws: false,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: true,
  },
});
