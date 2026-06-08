import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/api/, ""),
        timeout: 120000, // 120 seconds timeout for TTS synthesis
        proxyTimeout: 120000, // Additional timeout for proxy operations
        // Critical: pass through binary data untouched
        bypass: (req, res, options) => {
          if (req.headers.accept === 'audio/wav' || req.url.includes('/tts/')) {
            // Don't bypass /tts/ endpoints - let proxy handle them
            return null;
          }
        }
      }
    }
  }
});
