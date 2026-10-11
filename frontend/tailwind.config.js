/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        studio: {
          bg: "#090A0F",
          surface: "#0F111A",
          card: "#161926",
          cardHover: "#1D2132",
          border: "rgba(255, 255, 255, 0.08)",
          borderActive: "rgba(255, 255, 255, 0.18)",
          text: "#F1F5F9",
          muted: "#94A3B8",
          subtle: "#64748B",
        },
        accent: {
          emerald: "#10B981",
          cyan: "#06B6D4",
          amber: "#F59E0B",
          purple: "#8B5CF6",
        },
      },
      fontFamily: {
        sans: [
          '"Plus Jakarta Sans"',
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          "sans-serif",
        ],
        mono: [
          '"JetBrains Mono"',
          '"Fira Code"',
          "monospace",
        ],
      },
      boxShadow: {
        'bezel': '0 0 0 1px rgba(255,255,255,0.08), 0 8px 32px -4px rgba(0,0,0,0.4)',
        'glow-emerald': '0 0 24px -4px rgba(16, 185, 129, 0.25)',
        'glow-cyan': '0 0 24px -4px rgba(6, 182, 212, 0.25)',
      },
      animation: {
        'wave-bar': 'waveBar 1.2s ease-in-out infinite alternate',
        'pulse-subtle': 'pulseSubtle 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        waveBar: {
          '0%': { transform: 'scaleY(0.2)' },
          '100%': { transform: 'scaleY(1.0)' },
        },
        pulseSubtle: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
      },
    },
  },
  plugins: [],
};
