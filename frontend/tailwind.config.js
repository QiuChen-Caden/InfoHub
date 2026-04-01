/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0d1117',
        card: '#161b22',
        border: '#21262d',
        accent: '#58a6ff',
        text: '#c9d1d9',
        muted: '#8b949e',
      },
    },
  },
  plugins: [],
}
