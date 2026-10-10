import { describe, expect, it } from 'vitest';
import type { Dates } from './api';
import { shownDate, wantedDate } from './weekly';

const dates = { dates: [], latest: '2026-10-09' } as unknown as Dates;

describe('週次の基準日', () => {
  it('?date= が空や無いときは最新', () => {
    expect(wantedDate(null)).toBe('latest');
    expect(wantedDate('')).toBe('latest');
    expect(wantedDate('2026-10-02')).toBe('2026-10-02');
  });

  it('読めた週があればその週', () => {
    expect(shownDate('2026-10-02', 'latest', dates)).toBe('2026-10-02');
  });

  it('その週のデータが無くても、基準日は空にしない', () => {
    expect(shownDate(undefined, 'latest', dates)).toBe('2026-10-09');
    expect(shownDate(undefined, '2026-09-25', dates)).toBe('2026-09-25');
    expect(shownDate(undefined, 'latest', null)).toBe('');
  });
});
