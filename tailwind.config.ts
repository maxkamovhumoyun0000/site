import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./ui/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        background: "var(--paper)",
        foreground: "var(--ink-900)",
        surface: "var(--surface)",
        "surface-soft": "var(--surface-soft)",
        navy: {
          900: "var(--navy-900)",
          800: "var(--navy-800)",
          700: "var(--navy-700)",
        },
        gold: {
          500: "var(--gold-500)",
          400: "var(--gold-400)",
        },
        cyan: {
          500: "var(--cyan-500)",
          400: "var(--cyan-400)",
        },
        ink: {
          900: "var(--ink-900)",
          700: "var(--ink-700)",
          500: "var(--ink-500)",
        },
        line: {
          DEFAULT: "var(--line)",
          strong: "var(--line-strong)",
        },
        primary: "var(--navy-700)",
        "primary-foreground": "#ffffff",
        secondary: "var(--surface-soft)",
        "secondary-foreground": "var(--ink-900)",
        accent: "var(--cyan-500)",
        "accent-foreground": "#ffffff",
        muted: "var(--line)",
        "muted-foreground": "var(--ink-500)",
      },
      borderRadius: {
        xl: "var(--radius-xl)",
        lg: "var(--radius-lg)",
        md: "var(--radius-md)",
        sm: "var(--radius-sm)",
      },
      fontFamily: {
        sans: ["var(--font-base)", "sans-serif"],
        display: ["var(--font-display)", "sans-serif"],
      },
      boxShadow: {
        premium: "var(--shadow-md)",
        "premium-hover": "var(--shadow-lg)",
      },
      transitionTimingFunction: {
        premium: "var(--ease-premium)",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "slide-in-right": {
          "0%": { transform: "translateX(100%)" },
          "100%": { transform: "translateX(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.4s var(--ease-premium) forwards",
        "slide-in-right": "slide-in-right 0.3s var(--ease-premium) forwards",
      },
    },
  },
  plugins: [],
};

export default config;
