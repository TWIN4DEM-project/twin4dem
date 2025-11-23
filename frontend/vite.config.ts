import {resolve} from 'path'
import {defineConfig} from 'vite'
import react from '@vitejs/plugin-react'

const isDev = process.env.NODE_ENV !== "production";
const base = "/static/"
const devServerOrigin = "http://localhost:3000"
const devBase = `${devServerOrigin}${base}`

export default defineConfig({
    base: isDev ? devBase: base,
    root: ".",
    build: {
        manifest: true,
        outDir: "../backend/static/frontend",
        assetsDir: "assets",
        emptyOutDir: true,
        rollupOptions: {
            input: resolve("./src/main.tsx")
        },
        modulePreload: {
            polyfill: false
        }
    },
    server: {
        host: 'localhost',
        port: 3000,
        origin: "http://localhost:3000"
    },
    plugins: [
        react({
            babel: {
                plugins: [['babel-plugin-react-compiler']],
            },
        }),
    ],
})
