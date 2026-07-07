/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Radiant Red kept as a sparing accent (CTAs / urgency / destructive).
        radiant: "#E00000",
        // Re-point legacy names to the new CSS-var-driven tokens so untouched
        // files don't break mid-redesign.
        surface: "hsl(var(--muted))",

        // shadcn semantic tokens wired to CSS vars.
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },

        // Raw decorative scales for gradients / blobs.
        navy: {
          50: "#eef2f9",
          100: "#d6e0f0",
          200: "#adc1e0",
          300: "#7f9cce",
          400: "#5177b9",
          500: "#3459a0",
          600: "#264683",
          700: "#1d3767",
          800: "#152848",
          900: "#0e1c33",
          950: "#08111f",
        },
        teal: {
          50: "#eafbf7",
          100: "#cbf4ea",
          200: "#99e8d6",
          300: "#5fd4bd",
          400: "#2fb9a0",
          500: "#199e88",
          600: "#127e6e",
          700: "#12655a",
          800: "#13504a",
          900: "#13433e",
          950: "#052825",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["Sora", "Inter", "system-ui", "sans-serif"],
      },
      boxShadow: {
        soft: "0 1px 2px rgba(14,28,51,0.04), 0 4px 16px rgba(14,28,51,0.06)",
        elevated: "0 8px 30px rgba(14,28,51,0.10), 0 2px 8px rgba(14,28,51,0.06)",
        glow: "0 0 0 1px rgba(47,185,160,0.25), 0 8px 30px rgba(19,101,90,0.18)",
      },
      keyframes: {
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        "pulse-ring": {
          "0%": { boxShadow: "0 0 0 0 rgba(224,0,0,0.45)" },
          "70%": { boxShadow: "0 0 0 10px rgba(224,0,0,0)" },
          "100%": { boxShadow: "0 0 0 0 rgba(224,0,0,0)" },
        },
        "gradient-shift": {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        "count-blur-in": {
          from: { opacity: "0", filter: "blur(8px)", transform: "translateY(6px)" },
          to: { opacity: "1", filter: "blur(0)", transform: "translateY(0)" },
        },
      },
      animation: {
        shimmer: "shimmer 2s infinite",
        "pulse-ring": "pulse-ring 1.8s cubic-bezier(0.4,0,0.6,1) infinite",
        "gradient-shift": "gradient-shift 8s ease infinite",
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "count-blur-in": "count-blur-in 0.5s ease-out both",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
