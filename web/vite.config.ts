import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    // 開発中は API をサーバー(8765)に回す
    proxy: { '/api': 'http://127.0.0.1:8765' }
  }
});
