import adapter from '@sveltejs/adapter-static';

/** 静的な SPA に書き出す(詳細設計書 §8.1)。fallback を index.html にして、
 *  ファイルに当たらない URL は画面の側で解釈する。 */
export default {
  kit: {
    adapter: adapter({ fallback: 'index.html', pages: 'build', assets: 'build' }),
    prerender: { entries: [] }
  }
};
