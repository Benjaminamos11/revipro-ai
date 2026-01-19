import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: ["class"],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        border: "rgb(var(--border-color))", // mapped to CSS variable
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "rgb(var(--bg-primary))", // mapped to CSS variable
        foreground: "rgb(var(--text-primary))", // mapped to CSS variable
        primary: {
          DEFAULT: "rgb(var(--accent-primary))",
          foreground: "#ffffff",
        },
        secondary: {
          DEFAULT: "rgb(var(--bg-secondary))",
          foreground: "rgb(var(--text-primary))",
        },
        destructive: {
          DEFAULT: "rgb(var(--danger))",
          foreground: "#ffffff",
        },
        muted: {
          DEFAULT: "rgb(var(--bg-tertiary))",
          foreground: "rgb(var(--text-muted))",
        },
        accent: {
          DEFAULT: "rgb(var(--accent-secondary))",
          foreground: "#ffffff",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'Liberation Mono', 'Courier New', 'monospace'],
      },
    },
  },
  plugins: [],
}
export default config
