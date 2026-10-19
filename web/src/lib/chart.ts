/** グラフの共通の設定(詳細設計書 §8.4)。 */

/** スマホの横幅(基本設計書 §4.2)。 */
export const PHONE_MAX_WIDTH = 767;

export function isPhone(): boolean {
  return typeof window !== 'undefined' && window.innerWidth <= PHONE_MAX_WIDTH;
}

/** "07/20" → "7/20"(月と日の頭の 0 を落とす。2026-10-19)。 */
export function shortMonthDay(text: string): string {
  return text.replace(/(^|[^\d])0(\d)/g, '$1$2');
}

/** 週の横軸の文字。"07/20〜07/24" は "7/20〜7/24"、スマホでは週の初めの日 "7/20" だけにする。 */
export function weekTick(label: string, phone: boolean): string {
  return shortMonthDay(phone ? label.split('〜')[0] : label);
}

/**
 * 週の横軸の axisLabel。間引く数はグラフの横幅から ECharts に決めさせ(interval: 'auto')、
 * それでも重なる文字は出さない(hideOverlap)。
 * 以前は「約7個」と決め打ちしていたので、スマホの幅では日付が重なっていた(2026-10-19)。
 */
export function weekAxisLabel(color: string, phone = isPhone()) {
  return {
    color,
    fontSize: 10,
    interval: 'auto' as const,
    hideOverlap: true,
    formatter: (value: string) => weekTick(value, phone)
  };
}
