import { describe, expect, it } from 'vitest';
import type { VerdictRow } from './api';
import { buyCount, compare, DEFAULT_FILTERS, filter, PAGE_SIZE, RANK, sortKey } from './verdicts';

function row(partial: Partial<VerdictRow> & { v: VerdictRow['v'] }): VerdictRow {
  return {
    code: '0000', name: 'テスト', market: 'prime', s33: '7050', market_cap_oku: 5000,
    ...partial
  } as VerdictRow;
}

const ALL_NEUTRAL: VerdictRow['v'] = {
  granville: ['neutral', null],
  'earnings-breakout': ['neutral', null],
  'flag-pennant': ['neutral', null],
  'bollinger-bands': ['neutral', null],
  macd: ['neutral', null]
};

describe('買い判定の数(§8.6)', () => {
  it('食い違いも買いに数える(2026-09-26 確定)', () => {
    const r = row({ v: { ...ALL_NEUTRAL, granville: ['buy', null], 'flag-pennant': ['conflict', null] } });
    expect(buyCount(r)).toBe(2);
  });

  it('中立・売り・判定不能は数えない', () => {
    expect(buyCount(row({ v: ALL_NEUTRAL }))).toBe(0);
    expect(buyCount(row({ v: { ...ALL_NEUTRAL, macd: ['sell', null], granville: ['unknown', null] } }))).toBe(0);
  });
});

describe('並べ替え(§8.6)', () => {
  it('食い違いは並び順では判定不能と同じ位置', () => {
    expect(RANK.conflict).toBe(RANK.unknown);
  });

  it('手法ごとの順 → 最後に時価総額の大きい順', () => {
    const buy = row({ code: 'A', v: { ...ALL_NEUTRAL, granville: ['buy', null] }, market_cap_oku: 100 });
    const sell = row({ code: 'B', v: { ...ALL_NEUTRAL, granville: ['sell', null] }, market_cap_oku: 9999 });
    const small = row({ code: 'C', v: { ...ALL_NEUTRAL, granville: ['buy', null] }, market_cap_oku: 50 });
    const sorted = [sell, small, buy].sort((a, b) => compare(sortKey(a), sortKey(b)));
    expect(sorted.map((r) => r.code)).toEqual(['A', 'C', 'B']);
  });
});

describe('絞り込み(§8.6)', () => {
  const rows = [
    row({ code: 'BIG', market_cap_oku: 5000, v: { ...ALL_NEUTRAL, granville: ['buy', '買い③'] } }),
    row({ code: 'SMALL', market_cap_oku: 100, v: { ...ALL_NEUTRAL, granville: ['buy', '買い②'] } }),
    row({ code: 'GROWTH', market: 'growth', market_cap_oku: 2000, v: ALL_NEUTRAL })
  ];

  it('既定は時価総額 1,000 億円以上', () => {
    expect(filter(rows, DEFAULT_FILTERS).map((r) => r.code)).toEqual(['BIG', 'GROWTH']);
  });

  it('買い判定の数は「その数以上」', () => {
    const f = { ...DEFAULT_FILTERS, capMin: null, buyCount: 1 };
    expect(filter(rows, f).map((r) => r.code)).toEqual(['BIG', 'SMALL']);
  });

  it('局面は手法を選んだときだけ効く', () => {
    const f = { ...DEFAULT_FILTERS, capMin: null, method: 'granville', phases: ['買い②'] };
    expect(filter(rows, f).map((r) => r.code)).toEqual(['SMALL']);
  });

  it('市場と業種', () => {
    expect(filter(rows, { ...DEFAULT_FILTERS, capMin: null, market: 'growth' }).map((r) => r.code)).toEqual(['GROWTH']);
    expect(filter(rows, { ...DEFAULT_FILTERS, capMin: null, s33: '9999' })).toEqual([]);
  });

  it('1ページは50行', () => {
    expect(PAGE_SIZE).toBe(50);
  });
});
