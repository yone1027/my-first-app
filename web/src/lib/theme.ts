/** 色と書体(基本設計書 §4.8・詳細設計書 §8.4)。
 *
 *  値はコードに書かない。サーバーの `/api/theme`(config.toml の [theme])を
 *  既定とし、端末ごとの上書きを localStorage に持つ(設定画面 G-30)。
 *  どちらも CSS 変数として :root に流し込み、ECharts も同じ変数から読む。 */

import { api } from './api';

export const STORAGE_KEY = 'stockportal.theme';

/** 設定の項目名 → CSS 変数名。 */
export const CSS_VARS: Record<string, string> = {
  bg: '--bg',
  surface: '--surface',
  surface_alt: '--surface-alt',
  text: '--text',
  text_sub: '--text-sub',
  text_muted: '--text-muted',
  border: '--border',
  border_strong: '--border-strong',
  font_family: '--font-family',
  buy_bg: '--buy-bg',
  buy_fg: '--buy-fg',
  sell_bg: '--sell-bg',
  sell_fg: '--sell-fg',
  neutral_bg: '--neutral-bg',
  neutral_fg: '--neutral-fg',
  unknown_bg: '--unknown-bg',
  unknown_fg: '--unknown-fg',
  conflict_bg: '--conflict-bg',
  conflict_fg: '--conflict-fg',
  up: '--up',
  down: '--down',
  prime: '--prime',
  standard: '--standard',
  growth: '--growth'
};

/** 主体の6色は配列で来る。 */
export const INVESTOR_VARS = [0, 1, 2, 3, 4, 5].map((i) => `--investor-${i}`);

export type Theme = Record<string, string | string[]>;

let defaults: Theme = {};
let overrides: Theme = {};

export function loadOverrides(): Theme {
  if (typeof localStorage === 'undefined') return {};
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Theme) : {};
  } catch {
    return {};
  }
}

export function saveOverrides(next: Theme): void {
  overrides = next;
  if (typeof localStorage !== 'undefined') {
    if (Object.keys(next).length === 0) localStorage.removeItem(STORAGE_KEY);
    else localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }
  paint();
}

export function merged(): Theme {
  return { ...defaults, ...overrides };
}

export function defaultsOf(): Theme {
  return { ...defaults };
}

/** CSS 変数に流し込む。 */
export function paint(theme: Theme = merged()): void {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  for (const [key, cssVar] of Object.entries(CSS_VARS)) {
    const value = theme[key];
    if (typeof value === 'string') root.style.setProperty(cssVar, value);
  }
  const investors = theme.investors;
  if (Array.isArray(investors)) {
    investors.forEach((colour, i) => {
      if (INVESTOR_VARS[i]) root.style.setProperty(INVESTOR_VARS[i], colour);
    });
  }
}

let ready: Promise<void> | null = null;

/** 既定を取ってから上書きを重ねる。何度呼んでも読み込みは1回だけ。
 *
 *  レイアウトと各画面の両方から呼ばれる。子の onMount は親の await より先に
 *  走るので、画面側もこの Promise を待ってから値を読む。 */
export function init(fetcher?: typeof fetch): Promise<void> {
  if (ready) return ready;
  ready = (async () => {
    try {
      defaults = await api.theme(fetcher);
    } catch {
      defaults = {}; // 取れなくても CSS の初期値で動く
    }
    overrides = loadOverrides();
    paint();
  })();
  return ready;
}

/** CSS 変数の今の値(ECharts に渡す)。 */
export function cssValue(name: string, fallback = '#888888'): string {
  if (typeof document === 'undefined') return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

/** コントラスト比(設定画面で出す。基本設計書 §4.8.4)。 */
export function contrast(a: string, b: string): number | null {
  const la = luminance(a);
  const lb = luminance(b);
  if (la == null || lb == null) return null;
  const [hi, lo] = la > lb ? [la, lb] : [lb, la];
  return (hi + 0.05) / (lo + 0.05);
}

function luminance(hex: string): number | null {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return null;
  const channels = [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16) / 255);
  const linear = channels.map((c) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)));
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}
