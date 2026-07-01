export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Vazirmatn', 'system-ui', 'sans-serif'],
      },
      colors: {
        ivory: '#f7f3ec',
        champagne: '#efe7da',
        surface: '#fffdf9',
        ink: '#2b2722',
        muted: '#8a8178',
        gold: {
          DEFAULT: '#b5893f',
          soft: '#d9b878',
        },
        brown: '#3a2e23',
        agent: {
          content: '#9b5de5',
          sales: '#2f9e7e',
          support: '#2f7ed8',
          coordinator: '#d39a2c',
        },
      },
      boxShadow: {
        soft: '0 1px 2px rgba(43,39,34,0.04), 0 8px 24px -8px rgba(43,39,34,0.10)',
        lift: '0 2px 4px rgba(43,39,34,0.05), 0 18px 40px -12px rgba(43,39,34,0.18)',
        glow: '0 0 0 1px rgba(181,137,63,0.18), 0 12px 40px -10px rgba(181,137,63,0.35)',
      },
      borderRadius: {
        '2xl': '1.1rem',
        '3xl': '1.6rem',
      },
    },
  },
  plugins: [],
}