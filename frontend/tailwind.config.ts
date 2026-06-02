import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#f0f0ff",
          100: "#e0e0ff",
          200: "#c7c7fe",
          300: "#a3a3fd",
          400: "#7c7cfa",
          500: "#6366f1",
          600: "#5145e5",
          700: "#4338ca",
          800: "#3730a3",
          900: "#312e81",
        },
        dark: {
          bg: "#0B1120",
          card: "#111827",
          surface: "#1A2332",
          border: "#1E293B",
          text: "#E2E8F0",
          muted: "#94A3B8",
        },
        light: {
          bg: "#F8FAFC",
          card: "#FFFFFF",
          surface: "#F1F5F9",
          border: "#E2E8F0",
          text: "#1E293B",
          muted: "#64748B",
        },
        signal: {
          buy: "#10B981",
          add: "#3B82F6",
          watch: "#F59E0B",
          reduce: "#F97316",
          sell: "#EF4444",
        },
        accent: {
          cyan: "#06B6D4",
          emerald: "#10B981",
          amber: "#F59E0B",
          rose: "#F43F5E",
        },
      },
      borderRadius: {
        "2xl": "20px",
      },
      fontFamily: {
        mono: ["'JetBrains Mono'", "Menlo", "Monaco", "monospace"],
      },
      animation: {
        "skeleton-pulse": "skeleton-pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in": "fade-in 0.5s ease-out",
        "slide-up": "slide-up 0.5s ease-out",
        "glow": "glow 2s ease-in-out infinite alternate",
      },
      keyframes: {
        "skeleton-pulse": {
          "0%, 100%": { opacity: "0.4" },
          "50%": { opacity: "0.1" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "slide-up": {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "glow": {
          "0%": { boxShadow: "0 0 5px rgba(99, 102, 241, 0.3)" },
          "100%": { boxShadow: "0 0 20px rgba(99, 102, 241, 0.6)" },
        },
      },
    },
  },
  plugins: [],
};
export default config;
