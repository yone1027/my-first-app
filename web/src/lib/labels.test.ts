import { describe, expect, it } from 'vitest';
import { INVESTOR_ORDER, tradingViewUrl, VERDICT_LABEL, VERDICT_VARS } from './labels';

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
