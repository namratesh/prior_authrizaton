/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        radiant: "#E00000",
        surface: "#F5F7FA",
        border: "#E5E7EB",
      },
    },
  },
  plugins: [],
};
