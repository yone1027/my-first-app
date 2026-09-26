import { describe, expect, it } from 'vitest';
import { shares } from './shares';

describe('株数の目安(基本設計書 §6.10)', () => {
  it('文書の例のとおりに計算する', () => {
    // 資金 100万円、指値と損切りの差 100円 → 500株
    expect(shares(1_000_000, 2600, 2500)).toMatchObject({ riskLimit: 50_000, perShare: 100, shares: 500, unitShares: 500 });
    // 差が 300円 → 166株、単元では 100株
    expect(shares(1_000_000, 2800, 2500)).toMatchObject({ shares: 166, unitShares: 100 });
  });

  it('単元に満たないときは 0 株', () => {
    expect(shares(10_000, 2600, 2500)).toMatchObject({ shares: 5, unitShares: 0 });
  });

  it('資金や値段がないときは計算しない', () => {
    expect(shares(null, 2600, 2500).shares).toBeNull();
    expect(shares(1_000_000, null, 2500).shares).toBeNull();
    expect(shares(1_000_000, 2500, 2600).shares).toBeNull(); // 差が負
  });
});
