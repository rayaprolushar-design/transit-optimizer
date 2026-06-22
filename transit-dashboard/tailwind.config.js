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
        dark: {
          900: '#0B0F19', // Deep dark blue-grey background
          850: '#151D30', // Card background
          800: '#1E293B', // Border/Divider/Hover background
          700: '#334155',
        },
        brand: {
          primary: '#3B82F6', // Sleek blue
          success: '#10B981', // Accent emerald
          neonBlue: '#00E5FF',
          neonPurple: '#A855F7',
          neonPink: '#EC4899',
          neonAmber: '#F59E0B',
        }
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        display: ['Outfit', 'sans-serif'],
      },
      boxShadow: {
        'glass': '0 8px 32px 0 rgba(0, 0, 0, 0.5)',
        'neon-blue': '0 0 15px rgba(0, 229, 255, 0.3)',
        'neon-purple': '0 0 15px rgba(168, 85, 247, 0.3)',
        'neon-pink': '0 0 15px rgba(236, 72, 153, 0.3)',
      }
    },
  },
  plugins: [],
}
