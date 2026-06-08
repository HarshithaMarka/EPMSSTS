/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{js,jsx}"] ,
  theme: {
    extend: {
      colors: {
        base: {
          900: "#0B0F19",
          800: "#111827",
          700: "#1F2937",
          600: "#2B3648"
        },
        accent: {
          500: "#22D3EE",
          600: "#0EA5A4"
        },
        aura: {
          500: "#F59E0B",
          600: "#D97706"
        },
        emotion: {
          happy: "#22C55E",
          sad: "#3B82F6",
          angry: "#EF4444",
          neutral: "#94A3B8",
          fearful: "#F59E0B"
        }
      },
      boxShadow: {
        glow: "0 0 30px rgba(34, 211, 238, 0.25)",
        soft: "0 12px 30px rgba(15, 23, 42, 0.2)"
      },
      fontFamily: {
        sans: ["Sora", "system-ui", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif"],
        display: ["Space Grotesk", "Sora", "system-ui", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "Monaco", "Consolas", "Liberation Mono", "Courier New", "monospace"]
      }
    }
  },
  plugins: []
};
