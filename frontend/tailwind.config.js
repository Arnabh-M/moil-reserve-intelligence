/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: '#101a2b',
        navy2: '#16233a',
        orange: '#e0793a',
        'orange-soft': '#f2a768',
        teal: '#2a7f8c',
        bg: '#f4f6f9',
        border: '#e2e7ee',
      },
      fontFamily: {
        heading: ['"Roboto Slab"', 'serif'],
        body: ['Inter', 'sans-serif'],
      },
      borderRadius: {
        sm: '8px',
        DEFAULT: '8px',
        md: '12px',
      },
      boxShadow: {
        subtle: '0 1px 3px 0 rgba(20, 30, 50, 0.04)',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.4s ease-out',
      },
    },
  },
  plugins: [],
}
