/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: 'var(--background)',
        foreground: 'var(--foreground)',
        card: {
          DEFAULT: 'var(--card)',
          foreground: 'var(--card-foreground)',
        },
        popover: {
          DEFAULT: 'var(--popover)',
          foreground: 'var(--popover-foreground)',
        },
        primary: {
          DEFAULT: 'var(--primary)',
          foreground: 'var(--primary-foreground)',
        },
        secondary: {
          DEFAULT: 'var(--secondary)',
          foreground: 'var(--secondary-foreground)',
        },
        muted: {
          DEFAULT: 'var(--muted)',
          foreground: 'var(--muted-foreground)',
        },
        accent: {
          DEFAULT: 'var(--accent)',
          foreground: 'var(--accent-foreground)',
        },
        destructive: 'var(--destructive)',
        ring: 'var(--ring)',
        sidebar: {
          DEFAULT: 'var(--sidebar)',
          foreground: 'var(--sidebar-foreground)',
          primary: 'var(--sidebar-primary)',
          'primary-foreground': 'var(--sidebar-primary-foreground)',
          accent: 'var(--sidebar-accent)',
          'accent-foreground': 'var(--sidebar-accent-foreground)',
          border: 'var(--sidebar-border)',
        },
        log: {
          DEFAULT: 'var(--log-background)',
        },
        // legacy alias — maps to primary blue (Kite-style)
        brand: {
          50: 'color-mix(in oklch, var(--primary) 12%, var(--background))',
          100: 'color-mix(in oklch, var(--primary) 18%, var(--background))',
          300: 'color-mix(in oklch, var(--primary) 70%, var(--foreground))',
          600: 'var(--primary)',
          700: 'color-mix(in oklch, var(--primary) 85%, black)',
          950: 'color-mix(in oklch, var(--primary) 15%, var(--background))',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      borderColor: {
        DEFAULT: 'var(--border)',
        border: 'var(--border)',
        input: 'var(--input)',
        sidebar: 'var(--sidebar-border)',
      },
      ringColor: {
        DEFAULT: 'var(--ring)',
        ring: 'var(--ring)',
      },
      fontFamily: {
        sans: ['var(--font-sans)'],
        mono: ['var(--font-mono)'],
      },
    },
  },
  plugins: [],
}
