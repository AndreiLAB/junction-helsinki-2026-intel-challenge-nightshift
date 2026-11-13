/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        obsidian: {
          950: '#06080d',
          900: '#0b0f17',
          850: '#0f1420',
          800: '#141b2a',
          700: '#1e293b',
          border: '#1f2a3f',
        },
        intel: {
          blue: '#0071C5',
          light: '#00C7FD',
          dark: '#003C71',
          accent: '#00F5D4',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
      boxShadow: {
        'glow-intel': '0 0 15px -3px rgba(0, 199, 253, 0.35)',
        'glow-emerald': '0 0 15px -3px rgba(16, 185, 129, 0.35)',
        'glow-rose': '0 0 15px -3px rgba(244, 63, 94, 0.35)',
        'glow-amber': '0 0 15px -3px rgba(245, 158, 11, 0.35)',
      }
    },
  },
  plugins: [],
}
