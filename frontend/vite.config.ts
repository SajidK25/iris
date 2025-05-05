import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";

export default defineConfig(({ mode }) => {
  // Load environment variables based on mode
  const env = loadEnv(mode, process.cwd(), "VITE_");
  return {
    base: "/",
    server: {
      host: "::",
      port: 8080,
      watch: {
        usePolling: true,
        interval: 1000,
      },
      hmr: {
        overlay: true,
      },
    },
    plugins: [
      react(),
      mode === "development" && componentTagger(),
    ].filter(Boolean),
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    define: {
      // Ensure environment variables are available
      "process.env": env,
      __APP_ENV__: JSON.stringify(env),
    },
  };
});