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
        canvas: '#0b0f14',
        sidebar: '#0e131a',
        card: '#121922',
        surface: '#18212c',
        border: '#26313e',
        mint: {
          DEFAULT: '#55dbb1',
          bg: '#15352e',
        },
        rose: {
          accent: '#f28d95',
          bg: '#38232c',
        },
        amber: {
          accent: '#e9bf79',
          bg: '#352e21',
        },
        intel: {
          blue: '#0071C5',
          light: '#89b9ef',
          dark: '#003C71',
          accent: '#55dbb1',
          cpu: '#c4a7ea',
        },
        obsidian: {
          950: '#0b0f14',
          900: '#0e131a',
          850: '#121922',
          800: '#18212c',
          700: '#1e293b',
          border: '#26313e',
        },
        studio: {
          text: '#edf2f7',
          subtext: '#8e9bae',
          label: '#b5c0ce',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
      boxShadow: {
        'glow-intel': '0 0 15px -3px rgba(85, 219, 177, 0.35)',
        'glow-emerald': '0 0 15px -3px rgba(85, 219, 177, 0.35)',
        'glow-rose': '0 0 15px -3px rgba(242, 141, 149, 0.35)',
        'glow-amber': '0 0 15px -3px rgba(233, 191, 121, 0.35)',
      }
    },
  },
  plugins: [],
}
