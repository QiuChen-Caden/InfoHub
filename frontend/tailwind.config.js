/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    fontFamily: {
      mono: ['"JetBrains Mono"', 'Consolas', 'monospace'],
    },
    extend: {
      colors: {
        bg: '#000000',
        card: '#0a0a0a',
        border: '#333333',
        accent: '#FF8C00',
        text: '#FF8C00',
        muted: '#FF8C00',
        positive: '#00FF00',
        negative: '#FF0000',
        link: '#00FFFF',
        'header-bg': '#1a1a1a',
      },
      fontFamily: {
        sans: ['"JetBrains Mono"', 'Consolas', 'monospace'],
      },
      borderRadius: {
        DEFAULT: '0',
        sm: '0',
        md: '0',
        lg: '0',
        xl: '0',
        '2xl': '0',
        full: '0',
      },
      keyframes: {
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
      },
      animation: {
        blink: 'blink 1s step-end infinite',
      },
    },
  },
  plugins: [],
}
