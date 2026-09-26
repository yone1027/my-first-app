/** 判定表の絞り込みと並べ替え(詳細設計書 §8.6)。画面の中で行う。 */

import type { VerdictRow } from './api';

export const METHOD_KEYS = ['granville', 'earnings-breakout', 'flag-pennant', 'bollinger-bands', 'macd'];

/** 並べ替えのキー。食い違いは判定不能と同じ位置(2026-09-26 確定)。 */
export const RANK: Record<string, number> = {
  buy: 0,
  neutral: 1,
  unknown: 2,
  conflict: 2,
  sell: 3
};

export const BUY_COUNTS = [
  { value: 0, label: '指定なし' },
  { value: 5, label: '5' },
  { value: 4, label: '4' },
  { value: 3, label: '3' }
];

export type Filters = {
  buyCount: number;
  method: string;
  verdict: string;
  phases: string[];
  market: string;
  s33: string;
  capMin: number | null;
  capMax: number | null;
};

export const DEFAULT_FILTERS: Filters = {
  buyCount: 0,
  method: '',
  verdict: '',
  phases: [],
  market: '',
  s33: '',
  capMin: 1000, // 下限 1,000 億円(基本設計書 §5.4 (2))
  capMax: null
};

/** 「買い」判定の数。食い違いも買いに数える(2026-09-26 確定)。表には出さない。 */
export function buyCount(row: VerdictRow): number {
  let n = 0;
  for (const key of METHOD_KEYS) {
    const verdict = row.v[key]?.[0];
    if (verdict === 'buy' || verdict === 'conflict') n += 1;
  }
  return n;
}

/** 並べ替えのキーを1回だけ作る(§8.6 の 2)。 */
export function sortKey(row: VerdictRow): number[] {
  const parts = METHOD_KEYS.map((key) => RANK[row.v[key]?.[0] ?? 'unknown'] ?? 2);
  parts.push(-(row.market_cap_oku ?? 0));
  return parts;
}

export function compare(a: number[], b: number[]): number {
  for (let i = 0; i < a.length; i += 1) {
    if (a[i] !== b[i]) return a[i] - b[i];
  }
  return 0;
}

export function filter(rows: VerdictRow[], f: Filters): VerdictRow[] {
  return rows.filter((row) => {
    if (f.buyCount > 0 && buyCount(row) < f.buyCount) return false;
    if (f.method) {
      const [verdict, phase] = row.v[f.method] ?? [null, null];
      if (f.verdict && verdict !== f.verdict) return false;
      if (f.phases.length > 0 && (!phase || !f.phases.includes(phase))) return false;
    }
    if (f.market && row.market !== f.market) return false;
    if (f.s33 && row.s33 !== f.s33) return false;
    const cap = row.market_cap_oku;
    if (f.capMin != null && (cap == null || cap < f.capMin)) return false;
    if (f.capMax != null && (cap == null || cap > f.capMax)) return false;
    return true;
  });
}

export const PAGE_SIZE = 50; // 1ページ50行(2026-09-26 確定)
