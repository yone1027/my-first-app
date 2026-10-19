import { describe, expect, it } from 'vitest';
import { weekAxisLabel, weekTick } from './chart';

describe('週の横軸', () => {
  it('スマホでは週の初めの日だけ', () => {
    expect(weekTick('07/20〜07/24', true)).toBe('07/20');
    expect(weekTick('07/20〜07/24', false)).toBe('07/20〜07/24');
    expect(weekTick('07/20', true)).toBe('07/20');
  });

  it('間引きは横幅から決め、重なる文字は出さない', () => {
    const label = weekAxisLabel('#000', true);
    expect(label.interval).toBe('auto');
    expect(label.hideOverlap).toBe(true);
    expect(label.formatter('10/12〜10/16')).toBe('10/12');
  });
});
