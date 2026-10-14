/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./templates/**/*.html', './static/js/**/*.js'],
  theme: {
    extend: {
      colors: {
        ink: '#000000',
        panel: '#0c0c0c',
        raise: '#141414',
        line: '#232323',
        mute: '#8a8a8a',
        soft: '#a18cff',
        violet: { DEFAULT: '#6b49f0', deep: '#4d31c4' },
        sello: '#ff7a2f',
      },
      fontFamily: {
        sans: ['"Schibsted Grotesk"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
    },
  },
};
