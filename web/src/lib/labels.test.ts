import { describe, expect, it } from 'vitest';
import { INVESTOR_ORDER, OUTCOME_COLOR, OUTCOME_LABEL, outcomeText, tradingViewUrl, VERDICT_LABEL, VERDICT_VARS } from './labels';

describe('ラベル', () => {
  it('判定の5つに日本語と色がある', () => {
    for (const key of ['buy', 'neutral', 'sell', 'unknown', 'conflict']) {
      expect(VERDICT_LABEL[key]).toBeTruthy();
      expect(VERDICT_VARS[key].bg).toContain('var(--');
      expect(VERDICT_VARS[key].fg).toContain('var(--');
    }
  });

  it('主体は6つ', () => {
    expect(INVESTOR_ORDER).toHaveLength(6);
  });

  it('TradingView の URL は実機で確かめた形(§8.7)', () => {
    expect(tradingViewUrl('8306')).toBe('https://jp.tradingview.com/chart/?symbol=TSE%3A8306');
    expect(tradingViewUrl('285A')).toBe('https://jp.tradingview.com/chart/?symbol=TSE%3A285A');
    expect(tradingViewUrl('83060')).toBe('https://jp.tradingview.com/chart/?symbol=TSE%3A8306');
    expect(tradingViewUrl('287A0')).toBe('https://jp.tradingview.com/chart/?symbol=TSE%3A287A');
  });
});

describe('推奨銘柄の成績', () => {
  it('6つの状態すべてに日本語と色がある', () => {
    for (const key of ['ordering', 'unfilled', 'holding', 'win', 'lose', 'unknown']) {
      expect(OUTCOME_LABEL[key]).toBeTruthy();
      expect(OUTCOME_COLOR[key]).toContain('var(--');
    }
  });

  it('勝ち・負けには決済の理由を添える', () => {
    expect(outcomeText('win', 'target')).toBe('勝ち(目標)');
    expect(outcomeText('lose', 'time')).toBe('負け(期限)');
    expect(outcomeText('unfilled', null)).toBe('未約定');
  });
});
