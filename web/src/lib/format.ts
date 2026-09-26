/** 数値と日付の書式(基本設計書 §4.9・詳細設計書 §8.5)。
 *  値が null のときは「—」を返す(0 と区別する)。負の符号は − (U+2212)。 */

const DASH = '—';
const MINUS = '−';

function signed(text: string, value: number, withPlus = true): string {
  if (value < 0) return MINUS + text;
  return withPlus ? '+' + text : text;
}

/** 3桁区切りの整数。*/
export function int(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return DASH;
  return Math.round(value).toLocaleString('ja-JP');
}

/** 小数 digits 桁。*/
export function dec(value: number | null | undefined, digits = 1): string {
  if (value == null || !Number.isFinite(value)) return DASH;
  const text = Math.abs(value).toLocaleString('ja-JP', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  });
  return value < 0 ? MINUS + text : text;
}

/** 兆円。主体別の金額は小数2桁。*/
export function cho(yen: number | null | undefined, digits = 1): string {
  if (yen == null || !Number.isFinite(yen)) return DASH;
  return dec(yen / 1e12, digits) + '兆円';
}

/** 億円(整数・3桁区切り)。*/
export function oku(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value) ? DASH : int(value);
}

/** 割合(%)。増減には符号を付ける。*/
export function pct(value: number | null | undefined, digits = 1, withSign = false): string {
  if (value == null || !Number.isFinite(value)) return DASH;
  const text = dec(Math.abs(value), digits) + '%';
  return withSign ? signed(text, value) : (value < 0 ? MINUS + text : text);
}

/** 0〜1 の割合を % にする(picks の p_* / ev_*。§7.2)。*/
export function ratioPct(value: number | null | undefined, digits = 1, withSign = false): string {
  return value == null || !Number.isFinite(value) ? DASH : pct(value * 100, digits, withSign);
}

/** ポイント(pt)。小数1桁・符号付き。*/
export function pt(value: number | null | undefined, digits = 1): string {
  if (value == null || !Number.isFinite(value)) return DASH;
  return signed(dec(Math.abs(value), digits) + 'pt', value);
}

/** 倍(PER は小数1桁)。*/
export function times(value: number | null | undefined, digits = 2): string {
  return value == null || !Number.isFinite(value) ? DASH : dec(value, digits) + '倍';
}

/** 利回りの変化(bp・整数・符号付き)。*/
export function bp(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return DASH;
  return signed(int(Math.abs(value)) + 'bp', value);
}

/** パーセンタイル(0〜100 の整数)。*/
export function rank(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value) ? DASH : String(Math.round(value));
}

/** 株価・指数。*/
export function price(value: number | null | undefined, digits = 0): string {
  return value == null || !Number.isFinite(value) ? DASH : dec(value, digits);
}

const WEEKDAYS = ['月', '火', '水', '木', '金', '土', '日'];

/** 2026-09-18(金)。*/
export function dateWithWeekday(iso: string | null | undefined): string {
  if (!iso) return DASH;
  const d = new Date(iso + 'T00:00:00+09:00');
  return `${iso}(${WEEKDAYS[(d.getDay() + 6) % 7]})`;
}

/** 09/14〜09/18。*/
export function weekRange(start: string | null | undefined, end: string | null | undefined): string {
  if (!start || !end) return DASH;
  return `${start.slice(5).replace('-', '/')}〜${end.slice(5).replace('-', '/')}`;
}

/** 2026-09-26T04:52:10+09:00 → 2026-09-26 04:52。*/
export function stamp(iso: string | null | undefined): string {
  if (!iso) return DASH;
  return iso.slice(0, 10) + ' ' + iso.slice(11, 16);
}

export { DASH, MINUS };
