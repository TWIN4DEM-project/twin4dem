import { resolve } from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const isDev = process.env.NODE_ENV !== "production";
const base = "/static/";
const devServerOrigin = "http://localhost:3000";
const devBase = `${devServerOrigin}${base}`;

export default defineConfig({
  base: isDev ? devBase : base,
  root: ".",
  build: {
    manifest: true,
    outDir: isDev ? "../assets/frontend" : "dist",
    assetsDir: "assets",
    emptyOutDir: true,
    rollupOptions: {
      input: resolve("./src/main.tsx"),
    },
    modulePreload: {
      polyfill: false,
    },
  },
  server: {
    host: "0.0.0.0",
    port: 3000,
    origin: "http://localhost:3000",
  },
  plugins: [
    react({
      babel: {
        plugins: [["babel-plugin-react-compiler"]],
      },
    }),
  ],
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
      "@scss": resolve(__dirname, "../assets/scss"),
    },
  },
});
