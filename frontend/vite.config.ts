import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";
import svgLoader from "vite-svg-loader";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const basePath = env.VITE_APP_BASE_PATH || "/";
  const trimmedBase = basePath.replace(/\/+$/, "").replace(/^\/?/, "/");
  const apiPrefix = trimmedBase === "/" ? "/api" : `${trimmedBase}/api`;
  const proxyTarget = env.VITE_API_PROXY_TARGET || "http://127.0.0.1:5000";
  const proxyConfig: Record<string, { target: string; changeOrigin: boolean }> = {
    "/api": {
      target: proxyTarget,
      changeOrigin: true
    }
  };
  if (apiPrefix !== "/api") {
    proxyConfig[apiPrefix] = {
      target: proxyTarget,
      changeOrigin: true
    };
  }

  return {
    base: basePath.endsWith("/") ? basePath : `${basePath}/`,
    plugins: [vue(), svgLoader()],
    server: {
      host: true,
      port: 5173,
      proxy: proxyConfig
    }
  };
});
