/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        'display': ['JetBrains Mono', 'SF Mono', 'Monaco', 'monospace'],
        'sans': ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        // 深空主题配色
        'void': {
          50: '#f5f5f6',
          100: '#e5e5e7',
          200: '#cdced1',
          300: '#abadb2',
          400: '#82858c',
          500: '#676a71',
          600: '#575961',
          700: '#4a4b51',
          800: '#414246',
          900: '#39393d',
          950: '#0a0a0b',
        },
        'nebula': {
          purple: '#7c3aed',
          blue: '#3b82f6',
          cyan: '#06b6d4',
          pink: '#ec4899',
        }
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'float': 'float 6s ease-in-out infinite',
        'twinkle': 'twinkle 8s infinite',
        'slideUp': 'slideUp 0.3s ease',
        'shimmer': 'shimmer 1.5s infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        twinkle: {
          '0%, 100%': { opacity: '0.3' },
          '50%': { opacity: '0.5' },
        },
        slideUp: {
          'from': {
            opacity: '0',
            transform: 'translateY(10px)',
          },
          'to': {
            opacity: '1',
            transform: 'translateY(0)',
          },
        },
        shimmer: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        }
      }
    },
  },
  plugins: [
    require('tailwindcss-animate'),
  ],
}

