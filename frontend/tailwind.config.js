/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      colors: {
        // Light fintech surface system
        surface: {
          base: '#F7F8FA',
          raised: '#FFFFFF',
          overlay: '#F3F4F6',
          border: '#E5E7EB',
          hover: '#F9FAFB',
        },
        // Primary blue accent — refined professional
        accent: {
          DEFAULT: '#2563EB',
          hover: '#1D4ED8',
          light: '#EFF6FF',
          muted: '#93C5FD',
          border: '#BFDBFE',
        },
        // Text scale
        text: {
          primary: '#111827',
          secondary: '#374151',
          muted: '#6B7280',
          subtle: '#9CA3AF',
          placeholder: '#D1D5DB',
        },
        // Status colors — professional
        status: {
          pending: { text: '#1D4ED8', bg: '#EFF6FF', border: '#BFDBFE' },
          executing: { text: '#92400E', bg: '#FFFBEB', border: '#FDE68A' },
          completed: { text: '#065F46', bg: '#ECFDF5', border: '#A7F3D0' },
          failed: { text: '#991B1B', bg: '#FEF2F2', border: '#FECACA' },
          blocked: { text: '#92400E', bg: '#FFF7ED', border: '#FED7AA' },
          escalated: { text: '#7C2D12', bg: '#FFF7ED', border: '#FDBA74' },
        },
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideRight: {
          '0%': { opacity: '0', transform: 'translateX(-6px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        pulseSubtle: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.35s ease-out',
        'slide-right': 'slideRight 0.25s ease-out',
        'pulse-subtle': 'pulseSubtle 2s ease-in-out infinite',
      },
      boxShadow: {
        'card': '0 1px 3px 0 rgba(0,0,0,0.06), 0 1px 2px -1px rgba(0,0,0,0.04)',
        'card-hover': '0 4px 12px 0 rgba(0,0,0,0.08), 0 1px 3px 0 rgba(0,0,0,0.04)',
        'sidebar': '1px 0 0 0 #E5E7EB',
        'btn': '0 1px 2px 0 rgba(37,99,235,0.15)',
      },
    },
  },
  plugins: [],
}
