/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  safelist: [
    'border-l-blue-400',
    'border-l-purple-400',
    'border-l-amber-400',
    'border-l-green-400',
    'border-l-red-400',
    'border-l-gray-300',
    'border-l-gray-500',
    'dark:border-l-blue-400',
    'dark:border-l-purple-400',
    'dark:border-l-amber-400',
    'dark:border-l-green-400',
    'dark:border-l-red-400',
    'dark:border-l-gray-300',
    'dark:border-l-gray-500',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#eeedfe',
          100: '#cecbf6',
          400: '#7f77dd',
          600: '#534ab7',
          800: '#3c3489',
        },
      },
      fontFamily: {
        // App UI font - unchanged
        sans: ['Inter', 'system-ui', 'sans-serif'],
        // v2.3: landing page display font (headings, logo wordmark)
        syne: ['Syne', 'system-ui', 'sans-serif'],
        // v2.3: landing page body font
        dm: ['DM Sans', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
