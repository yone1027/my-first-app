/** 株数の目安(基本設計書 §6.10・詳細設計書 §8.8)。 */

export const RISK_LIMIT = 0.05; // 1回のリスク上限は投資資金の5%
export const UNIT = 100; // 単元

export type Shares = {
  riskLimit: number;
  perShare: number | null;
  shares: number | null;
  unitShares: number | null;
};

export function shares(capital: number | null, entry: number | null, stop: number | null): Shares {
  const riskLimit = (capital ?? 0) * RISK_LIMIT;
  const perShare = entry != null && stop != null ? entry - stop : null;
  if (!capital || perShare == null || perShare <= 0) {
    return { riskLimit, perShare, shares: null, unitShares: null };
  }
  const raw = Math.floor(riskLimit / perShare);
  return { riskLimit, perShare, shares: raw, unitShares: Math.floor(raw / UNIT) * UNIT };
}

export const CAPITAL_KEY = 'stockportal.capital';

export function loadCapital(): number | null {
  if (typeof localStorage === 'undefined') return null;
  const raw = localStorage.getItem(CAPITAL_KEY);
  const value = raw ? Number(raw) : NaN;
  return Number.isFinite(value) && value > 0 ? value : null;
}

export function saveCapital(value: number | null): void {
  if (typeof localStorage === 'undefined') return;
  if (value && value > 0) localStorage.setItem(CAPITAL_KEY, String(value));
  else localStorage.removeItem(CAPITAL_KEY);
}
