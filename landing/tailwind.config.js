/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./script.js"],
  theme: {
    extend: {
      colors: {
        brand: {
          primary: "#1B4F65",
          "primary-hover": "#16404F",
          accent: "#7AC1A2",
          "accent-light": "#DAF0E6",
          bg: "#F7FAF9",
          surface: "#FFFFFF",
          text: "#102B36",
          "text-muted": "#4A6B77",
          border: "#C8E0D8"
        }
      }
    }
  }
};

