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
          50: "#F5F3FF",
          100: "#EDE9FE",
          200: "#DDD6FE",
          300: "#C4B5FD",
          400: "#A78BFA",
          500: "#8B5CF6",
          600: "#7C3AED",
          700: "#6D28D9",
          800: "#5B21B6",
          900: "#4C1D95",
        },
        dark: {
          bg: "#F6F8FB",
          card: "#FFFFFF",
          surface: "#F1F5F9",
          border: "#D8DEE9",
          text: "#0F172A",
          muted: "#64748B",
        },
        light: {
          bg: "#F6F8FB",
          card: "#FFFFFF",
          surface: "#F1F5F9",
          border: "#D8DEE9",
          text: "#0F172A",
          muted: "#64748B",
        },
        signal: {
          buy: "#047857",
          add: "#1D4ED8",
          watch: "#92400E",
          reduce: "#C2410C",
          sell: "#B91C1C",
        },
        accent: {
          cyan: "#0E7490",
          emerald: "#047857",
          amber: "#92400E",
          rose: "#BE123C",
        },
      },
      borderRadius: {
        "2xl": "16px",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "PingFang SC", "Microsoft YaHei", "Noto Sans SC", "sans-serif"],
        mono: ["'JetBrains Mono'", "Menlo", "Monaco", "monospace"],
      },
      fontSize: {
        "title": ["32px", { lineHeight: "1.2", fontWeight: "700" }],
        "h1": ["24px", { lineHeight: "1.3", fontWeight: "700" }],
        "h2": ["20px", { lineHeight: "1.3", fontWeight: "600" }],
        "h3": ["17px", { lineHeight: "1.4", fontWeight: "600" }],
      },
      animation: {
        "skeleton-pulse": "skeleton-pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in": "fade-in 0.3s ease-out",
        "slide-up": "slide-up 0.3s ease-out",
      },
      keyframes: {
        "skeleton-pulse": {
          "0%, 100%": { opacity: "0.6" },
          "50%": { opacity: "0.3" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "slide-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
export default config;
