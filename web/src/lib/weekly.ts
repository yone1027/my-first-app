/** 週次の3画面で共通の、基準日の扱い(基本設計書 §5.4)。 */

import type { Dates } from './api';

/** URL の ?date= から、API に渡す基準日を決める。空や無いときは最新。 */
export function wantedDate(param: string | null): string {
  return param || 'latest';
}

/**
 * 見出しとタブに出す基準日。その週にデータが無くて本文が読めなくても、
 * タブのリンクや ◀▶ が ?date= の空にならないようにする。
 */
export function shownDate(loaded: string | undefined, wanted: string, dates: Dates | null): string {
  if (loaded) return loaded;
  if (wanted !== 'latest') return wanted;
  return dates?.latest ?? '';
}
