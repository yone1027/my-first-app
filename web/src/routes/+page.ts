import { redirect } from '@sveltejs/kit';

/** 最初に開く画面は G-11 日本市場(基本設計書 §2)。 */
export function load({ url }: { url: URL }) {
  const period = url.searchParams.get('period');
  throw redirect(307, period ? `/market?period=${period}` : '/market');
}
