import {resolve} from 'path'
import {defineConfig} from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
    base: "/static/",
    build: {
        manifest: true,
        outDir: resolve("./dist"),
        rollupOptions: {
            input: resolve("./src/main.tsx")
        },
        modulePreload: {
            polyfill: false
        }
    },
    server: {
        host: 'localhost',
        port: 3000
    },

    plugins: [
        react({
            babel: {
                plugins: [['babel-plugin-react-compiler']],
            },
        }),
    ],
})
