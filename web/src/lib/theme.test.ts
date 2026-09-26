import { describe, expect, it } from 'vitest';
import { contrast, CSS_VARS, INVESTOR_VARS } from './theme';

describe('テーマ(基本設計書 §4.8)', () => {
  it('基本設計書に並ぶ色が CSS 変数に対応している', () => {
    for (const key of [
      'bg', 'surface', 'text', 'text_sub', 'text_muted', 'border', 'font_family',
      'buy_bg', 'buy_fg', 'sell_bg', 'sell_fg', 'neutral_bg', 'neutral_fg',
      'unknown_bg', 'unknown_fg', 'conflict_bg', 'conflict_fg', 'prime', 'standard', 'growth'
    ]) {
      expect(CSS_VARS[key]).toBeTruthy();
    }
    expect(INVESTOR_VARS).toHaveLength(6);
  });

  it('コントラスト比が基本設計書の表と一致する', () => {
    expect(contrast('#F7E3DC', '#B1442A')).toBeCloseTo(4.55, 1);
    expect(contrast('#DFE9F2', '#2F6690')).toBeCloseTo(4.99, 1);
    expect(contrast('#EEECE6', '#57534A')).toBeCloseTo(6.48, 1);
    expect(contrast('#FFFFFF', '#6B675E')).toBeCloseTo(5.63, 1);
    expect(contrast('#F0E4EE', '#7A4B72')).toBeCloseTo(5.54, 1);
  });

  it('画面案のままの買いの色は基準に届かない(変えた理由)', () => {
    expect(contrast('#F7E3DC', '#B5452B')!).toBeLessThan(4.5);
  });

  it('色でない文字列は null', () => {
    expect(contrast('赤', '#FFFFFF')).toBeNull();
  });
});
