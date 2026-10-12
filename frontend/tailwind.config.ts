import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#e7eef6",
        muted: "#93a4b8",
        line: "#314155",
        canvas: "#10151c",
        panel: "#182230",
        panel2: "#223044",
        amber: "#e2a34a",
        teal: "#7eb8a8",
        coral: "#e07a5f",
      },
      fontFamily: {
        display: ["var(--font-display)", "Palatino", "Georgia", "serif"],
        sans: ["var(--font-body)", "Segoe UI", "sans-serif"],
      },
      boxShadow: {
        panel: "0 18px 50px rgba(0, 0, 0, 0.28)",
      },
    },
  },
  plugins: [],
};

export default config;
