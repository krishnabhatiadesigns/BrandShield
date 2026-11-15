/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0f7f2',
          100: '#dcebe1',
          200: '#bcd8c6',
          300: '#8fbda2',
          400: '#5f9c7a',
          500: '#3f7f5c',
          600: '#2d6547',
          700: '#1F5C3A',
          800: '#1a4a30',
          900: '#163d28',
        },
        gold: {
          400: '#f0b95e',
          500: '#E8A33D',
          600: '#d18f2c',
        },
        cream: '#F5EFE3',
        charcoal: '#2B2B2B',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
