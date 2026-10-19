import { describe, expect, it } from 'vitest';
import { shortMonthDay, weekAxisLabel, weekTick } from './chart';

describe('週の横軸', () => {
  it('スマホでは週の初めの日だけ', () => {
    expect(weekTick('07/20〜07/24', true)).toBe('7/20');
    expect(weekTick('07/20〜07/24', false)).toBe('7/20〜7/24');
    expect(weekTick('07/20', true)).toBe('7/20');
  });

  it('間引きは横幅から決め、重なる文字は出さない', () => {
    const label = weekAxisLabel('#000', true);
    expect(label.interval).toBe('auto');
    expect(label.hideOverlap).toBe(true);
    expect(label.formatter('10/12〜10/16')).toBe('10/12');
  });

  it('月と日の頭の 0 を落とす', () => {
    expect(shortMonthDay('09/07')).toBe('9/7');
    expect(shortMonthDay('10/05〜10/09')).toBe('10/5〜10/9');
    expect(shortMonthDay('12/30〜01/02')).toBe('12/30〜1/2');
    expect(shortMonthDay('10/10')).toBe('10/10');
  });
});
