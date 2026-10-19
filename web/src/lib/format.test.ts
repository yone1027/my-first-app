import { describe, expect, it } from 'vitest';
import * as f from './format';

describe('書式(基本設計書 §4.9)', () => {
  it('値がないときは「—」', () => {
    for (const fn of [f.int, f.dec, f.cho, f.pct, f.pt, f.times, f.bp, f.price, f.rank]) {
      expect(fn(null)).toBe('—');
      expect(fn(undefined)).toBe('—');
    }
    expect(f.dateWithWeekday(null)).toBe('—');
    expect(f.weekRange('2026-09-14', null)).toBe('—');
  });

  it('0 は「—」と区別する', () => {
    expect(f.int(0)).toBe('0');
    expect(f.pct(0)).toBe('0.0%');
  });

  it('3桁区切り', () => {
    expect(f.int(250544)).toBe('250,544');
    expect(f.price(2498)).toBe('2,498');
    expect(f.price(2581, 1)).toBe('2,581.0');
  });

  it('負の符号は − (U+2212)', () => {
    expect(f.pct(-5.6)).toBe('−5.6%');
    expect(f.pt(-1.2)).toBe('−1.2pt');
    expect(f.bp(-17)).toBe('−17bp');
  });

  it('増減には符号を付ける', () => {
    expect(f.pct(18, 0, true)).toBe('+18%');
    expect(f.pt(1.2)).toBe('+1.2pt');
    expect(f.bp(17)).toBe('+17bp');
  });

  it('兆円は小数1桁、主体別は2桁', () => {
    expect(f.cho(3.37e13)).toBe('33.7兆円');
    expect(f.cho(1.52e12, 2)).toBe('1.52兆円');
  });

  it('割合(0〜1)を % にする', () => {
    expect(f.ratioPct(0.4995453718857977)).toBe('50.0%');
    expect(f.ratioPct(0.023877415949654254)).toBe('2.4%');
    expect(f.ratioPct(0.011927852630241912)).toBe('1.2%');
  });

  it('PER は小数1桁', () => {
    expect(f.times(15.3, 1)).toBe('15.3倍');
    expect(f.times(1.11)).toBe('1.11倍');
  });

  it('日付と週', () => {
    const today = new Date('2026-10-20T12:00:00+09:00');
    expect(f.dateWithWeekday('2026-09-18', today)).toBe('9/18(金)');
    expect(f.dateWithWeekday('2025-09-18', today)).toBe('2025/9/18(木)');
    expect(f.weekRange('2026-09-14', '2026-09-18')).toBe('9/14〜9/18');
    expect(f.weekRange('2026-09-28', '2026-10-02')).toBe('9/28〜10/2');
    expect(f.monthDay('2026-09-08')).toBe('9/8');
    expect(f.monthDayWeekday('2026-09-18')).toBe('9/18(金)');
    expect(f.stamp('2026-09-26T04:52:10+09:00', today)).toBe('9/26 04:52');
  });

  it('年をまたぐかもしれない日付は、ほかの年のときだけ年を付ける', () => {
    const today = new Date('2026-10-20T12:00:00+09:00');
    expect(f.dateShort('2026-09-08', today)).toBe('9/8');
    expect(f.dateShort('2025-12-01', today)).toBe('2025/12/1');
    expect(f.dateShort('週足', today)).toBe('週足');
    expect(f.datesInText('高値 1,534(2026-10-09) / 安値 1,351(2025-09-04)', today)).toBe('高値 1,534(10/9) / 安値 1,351(2025/9/4)');
    expect(f.datesInText(null, today)).toBe('');
  });
});
