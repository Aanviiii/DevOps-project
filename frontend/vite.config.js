import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the Vite server forwards /api to a local backend; in containers nginx
// does the same job, so the browser only ever talks to its own origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  build: {
    sourcemap: false,
  },
});
