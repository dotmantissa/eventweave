import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  envDir: "../..",
  server: {
    proxy: { "/api": { target: "http://localhost:4317", changeOrigin: true } },
  },
  build: {
    target: "es2022",
    chunkSizeWarningLimit: 1500,
  },
  define: {
    "import.meta.env.VITE_PRIVY_APP_ID": JSON.stringify(
      loadEnv(mode, "../..", "VITE_").VITE_PRIVY_APP_ID || "",
    ),
  },
}));
