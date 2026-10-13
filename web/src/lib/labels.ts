/** 画面に出す日本語のラベル。API は記号で返す(§5.4)。 */

export const VERDICT_LABEL: Record<string, string> = {
  buy: '買い',
  neutral: '中立',
  sell: '売り',
  unknown: '判定不能',
  conflict: '食い違い'
};

/** 判定ごとの CSS 変数の組(基本設計書 §4.8.2)。 */
export const VERDICT_VARS: Record<string, { bg: string; fg: string }> = {
  buy: { bg: 'var(--buy-bg)', fg: 'var(--buy-fg)' },
  neutral: { bg: 'var(--neutral-bg)', fg: 'var(--neutral-fg)' },
  sell: { bg: 'var(--sell-bg)', fg: 'var(--sell-fg)' },
  unknown: { bg: 'var(--unknown-bg)', fg: 'var(--unknown-fg)' },
  conflict: { bg: 'var(--conflict-bg)', fg: 'var(--conflict-fg)' }
};

export const SEGMENT_LABEL: Record<string, string> = {
  prime: 'プライム',
  standard: 'スタンダード',
  growth: 'グロース',
  all: '全市場'
};

export const INVESTOR_LABEL: Record<string, string> = {
  foreigners: '海外投資家',
  individuals: '個人',
  investment_trusts: '投資信託',
  business_cos: '事業法人',
  trust_banks: '信託銀行',
  proprietary: '証券会社の自己売買'
};

export const INVESTOR_ORDER = [
  'foreigners', 'individuals', 'investment_trusts', 'business_cos', 'trust_banks', 'proprietary'
];

export const INDICATOR_LABEL: Record<string, { name: string; unit: string }> = {
  jgb10y: { name: '10年国債利回り', unit: '%' },
  usdjpy: { name: 'ドル円', unit: '円' },
  wti: { name: 'WTI 原油', unit: 'ドル' }
};

export const PERIODS = [
  { key: '13w', label: '13週' },
  { key: '26w', label: '26週' },
  { key: '52w', label: '52週' }
];

/** 各画面に常に出す注意書き(要件 R6)。 */
export const CAUTIONS = [
  'どの手法も較正していない。売買判断として使えるものではない',
  '確率は推定値で、保証ではない',
  '検証では銘柄選定の優位性は確認できていない'
];

/** TradingView で開くリンク(§8.7)。5文字で末尾が 0 のときは落とす。 */
export function tradingViewUrl(code: string): string {
  const symbol = code.length === 5 && code.endsWith('0') ? code.slice(0, 4) : code;
  return `https://jp.tradingview.com/chart/?symbol=TSE%3A${symbol}`;
}

/** 推奨銘柄の成績の状態(§6.11)。勝ち・負けは損益の符号で決まる(期限の売りも含む)。 */
export const OUTCOME_LABEL: Record<string, string> = {
  ordering: '注文中',
  unfilled: '未約定',
  holding: '保有中',
  win: '勝ち',
  lose: '負け',
  unknown: '評価できない'
};

export const REASON_LABEL: Record<string, string> = {
  target: '目標',
  stop: '損切り',
  time: '期限'
};

/** 状態の文字色。勝ちは上げ、負けは下げの色。 */
export const OUTCOME_COLOR: Record<string, string> = {
  win: 'var(--up)',
  lose: 'var(--down)',
  holding: 'var(--text)',
  ordering: 'var(--text-sub)',
  unfilled: 'var(--text-muted)',
  unknown: 'var(--text-muted)'
};

/** 「勝ち(目標)」のように理由を添える。 */
export function outcomeText(status: string, reason: string | null | undefined): string {
  const label = OUTCOME_LABEL[status] ?? status;
  return reason && REASON_LABEL[reason] ? `${label}(${REASON_LABEL[reason]})` : label;
}
