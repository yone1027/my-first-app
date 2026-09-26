import { defineConfig } from 'vitest/config';

/** 書式などの素の TypeScript を試す。画面の組み立ては SvelteKit の build で確かめる。 */
export default defineConfig({
  test: { environment: 'node', include: ['src/**/*.test.ts'] }
});
