/** グラフの共通の設定(詳細設計書 §8.4)。 */

/** スマホの横幅(基本設計書 §4.2)。 */
export const PHONE_MAX_WIDTH = 767;

export function isPhone(): boolean {
  return typeof window !== 'undefined' && window.innerWidth <= PHONE_MAX_WIDTH;
}

/** 週の横軸の文字。"07/20〜07/24" のうち、スマホでは週の初めの日だけにする。 */
export function weekTick(label: string, phone: boolean): string {
  return phone ? label.split('〜')[0] : label;
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
