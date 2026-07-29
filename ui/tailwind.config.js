/**
 * Beyond Style UAE brand system (official brandbook by Pomelli):
 *   Doe Brown #C5A059 · Jet Black #000000 · Pure White #FFFFFF
 *   Primary typeface Cinzel · Secondary typeface Montserrat
 * Neutral stone scale retained for surfaces; gold is the single accent.
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#000000",
        gold: {
          DEFAULT: "#C5A059",
          soft: "#d8bc82",
          deep: "#a5813f",
        },
        stone: {
          25: "#fbfaf8",
          50: "#f6f4f0",
          100: "#edeae3",
          200: "#ddd8cd",
          300: "#c3bcae",
          400: "#98907f",
          500: "#6f6757",
        },
        accent: "#C5A059",
        amber: { flag: "#a5813f" },
        deny: "#9c3d2e",
        ok: "#4c6b52",
      },
      fontFamily: {
        display: ["Cinzel", "Georgia", "'Times New Roman'", "serif"],
        body: [
          "Montserrat", "system-ui", "-apple-system", "'Segoe UI'",
          "'Noto Sans Arabic'", "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
