/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0b0f14",
        panel: "#111821",
        panel2: "#0e141c",
        line: "#1e2a38",
        ink: "#d7e0ea",
        muted: "#7f8fa3",
        accent: "#3dd68c",
        warn: "#f0b429",
      },
      fontFamily: {
        mono: ['"IBM Plex Mono"', '"JetBrains Mono"', "ui-monospace", "Menlo", "monospace"],
        sans: ['"IBM Plex Sans"', '"Segoe UI"', "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
