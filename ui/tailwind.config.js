/** Quiet-luxury neutrals: stone, ivory, charcoal, one muted accent. */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#2b2926",
        stone: {
          25: "#faf9f7",
          50: "#f5f3f0",
          100: "#eceae5",
          200: "#dcd8d1",
          300: "#c2bcb2",
          400: "#989083",
          500: "#6f6759",
        },
        accent: "#7d6748",
        amber: { flag: "#b0722a" },
        deny: "#9c3d2e",
        ok: "#4c6b52",
      },
      fontFamily: {
        display: ["Georgia", "'Times New Roman'", "serif"],
        body: [
          "system-ui", "-apple-system", "'Segoe UI'", "Roboto",
          "'Noto Sans Arabic'", "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
