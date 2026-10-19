/**
 * クラウド版の API(詳細設計書 §13.4)。Pages Functions から使う、入出力を持たない部分。
 *
 * Mac で書き出した JSON(/_data/…)を、今の API と同じ URL・同じ応答で返す。
 * ファイル名の決め方は server/stockportal/batch/publish/export.py と合わせる。
 */

export const PERIODS = ['13w', '26w', '52w'];
export const DEFAULT_PERIOD = '13w';
export const SCOPES = ['all', 'prime', 'standard', 'growth'];
export const DEFAULT_SCOPE = 'all';
export const SEARCH_LIMIT = 10;
export const SEARCH_MAX_LENGTH = 64;

const pick = (value, allowed, fallback) => (allowed.includes(value) ? value : fallback);

/** 5文字で末尾が 0 のときは末尾を落とす(jq.short_code と同じ)。 */
export function shortCode(code) {
  const c = (code ?? '').trim();
  return c.length === 5 && c.endsWith('0') ? c.slice(0, -1) : c;
}

/** 根拠のファイルの分け方(export.detail_shard と同じ)。 */
export function detailShard(code) {
  return code.slice(0, 2).toUpperCase() || '_';
}

/**
 * URL(/api の後ろ)を、返すものに対応させる。
 *   { kind: 'file', key }            … /_data/<key> をそのまま返す
 *   { kind: 'detail', key, code }    … /_data/<key> の中から1銘柄
 *   { kind: 'weekly', date, rest }   … 基準日を確かめてから決める(resolveWeekly)
 *   { kind: 'status' | 'search' | 'health' }
 *   { kind: 'error', status, body }
 */
export function route(path, params) {
  const parts = path.split('/').filter(Boolean);
  const [head, ...rest] = parts;
  if (head === 'health' && rest.length === 0) return { kind: 'health' };
  if (head === 'status' && rest.length === 0) return { kind: 'status' };
  if (head === 'search' && rest.length === 0) return { kind: 'search' };
  if (head === 'theme' && rest.length === 0) return { kind: 'file', key: 'theme.json' };
  if (head === 'market' && rest.length === 1) {
    const period = pick(params.get('period'), PERIODS, DEFAULT_PERIOD);
    if (rest[0] === 'japan' || rest[0] === 'segments') return { kind: 'file', key: `market/${rest[0]}.${period}.json` };
    if (rest[0] === 'sectors') {
      const scope = pick(params.get('scope'), SCOPES, DEFAULT_SCOPE);
      return { kind: 'file', key: `market/sectors.${period}.${scope}.json` };
    }
  }
  if (head === 'weekly') {
    if (rest.length === 1 && (rest[0] === 'dates' || rest[0] === 'evaluation')) {
      return { kind: 'file', key: `weekly/${rest[0]}.json` };
    }
    if (rest.length === 2 && ['verdicts', 'picks', 'candidates'].includes(rest[1])) {
      return { kind: 'weekly', date: rest[0], rest: rest.slice(1) };
    }
    if (rest.length === 3 && rest[1] === 'verdicts') return { kind: 'weekly', date: rest[0], rest: rest.slice(1) };
  }
  return { kind: 'error', status: 404, body: { error: 'not_found' } };
}

/** 基準日を確かめる(api/weekly.py の resolve_date と同じ)。dates は dates.json の中身。 */
export function resolveWeekly(found, dates) {
  const list = (dates?.dates ?? []).map((d) => d.date);
  if (list.length === 0) return { kind: 'error', status: 404, body: { error: 'no_data', detail: 'screen' } };
  let date = found.date;
  if (date === 'latest' || date === '') date = list[0];
  else if (!list.includes(date)) return { kind: 'error', status: 404, body: { error: 'no_such_date', latest: list[0] } };
  const [what, code] = found.rest;
  if (code === undefined) return { kind: 'file', key: `weekly/${date}/${what}.json` };
  return { kind: 'detail', key: `weekly/${date}/detail/${detailShard(code)}.json`, code };
}

/** 根拠のファイルから1銘柄を取り出す(api/weekly.py の verdict_detail と同じく、末尾 0 付きも探す)。 */
export function pickDetail(entries, code) {
  const found = entries?.[code] ?? entries?.[shortCode(code)] ?? entries?.[`${code}0`];
  if (found) return { status: 200, body: found };
  return { status: 404, body: { error: 'no_data', detail: `verdicts/${code}` } };
}

// ---- 検索(api/search.py と同じ並べ方)----

/** NFKC で正規化し、英字は大文字にする。 */
export function normalize(text) {
  return (text ?? '').normalize('NFKC').toUpperCase().trim();
}

const isAlnum = (text) => /^[\p{L}\p{N}]+$/u.test(text);

export function search(index, q) {
  const query = normalize(q);
  if (!query) return [];
  const universe = new Set(index?.universe ?? []);
  const length = [...query].length;
  const codeLike = length >= 4 && length <= 5 && isAlnum(query);
  const prefix = shortCode(query);
  const hits = [];
  for (const row of index?.rows ?? []) {
    if (codeLike && row.code.startsWith(prefix)) {
      hits.push([0, 0, row]);
      continue;
    }
    const position = row.name_key.indexOf(query);
    if (position >= 0) hits.push([1, position, row]);
  }
  hits.sort((a, b) => a[0] - b[0] || a[1] - b[1] || (a[2].code < b[2].code ? -1 : a[2].code > b[2].code ? 1 : 0));
  return hits.slice(0, SEARCH_LIMIT).map(([, , r]) => ({
    code: r.code,
    name: r.name,
    market: r.market,
    in_universe: universe.has(r.code)
  }));
}

// ---- データの時点と「更新が遅れています」(api/status.py と同じ判定)----

const JST_OFFSET_MS = 9 * 60 * 60 * 1000;

/** 日本時間の "YYYY-MM-DDTHH:MM"(文字列のまま大小を比べられる)。 */
export function jstStamp(now) {
  return new Date(now.getTime() + JST_OFFSET_MS).toISOString().slice(0, 16);
}

function addDays(day, n) {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

/** その日を含む週の月曜(Python の weekday() と同じく月=0)。 */
function mondayOf(day) {
  const weekday = (new Date(`${day}T00:00:00Z`).getUTCDay() + 6) % 7;
  return addDays(day, -weekday);
}

export function computeStatus(base, now) {
  const stamp = jstStamp(now);
  const cutoff = base.cutoff ?? '17:00';
  let expected = null;
  for (const end of base.week_ends ?? []) {
    if (`${end}T${cutoff}` <= stamp) expected = end;
  }
  let pastCutoff = false;
  if (expected) {
    const target = addDays(mondayOf(expected), base.schedule.weekday);
    pastCutoff = stamp >= `${target}T${base.schedule.at}`;
  }
  const marketWeek = base.market?.data_week_end ?? null;
  const latest = base.weekly?.latest_date ?? null;
  const steps = base.weekly?.steps ?? {};
  const stepFailed = Object.values(steps).some((v) => v === 'failed' || v === 'timeout');
  return {
    now: `${stamp}:00+09:00`,
    expected_week_end: expected,
    delayed_after: base.delayed_after,
    market: {
      data_week_end: marketWeek,
      last_updated: base.market?.last_updated ?? null,
      delayed: Boolean(pastCutoff && expected && (marketWeek ?? '') < expected)
    },
    weekly: {
      latest_date: latest,
      last_updated: base.weekly?.last_updated ?? null,
      delayed: Boolean(pastCutoff && expected && (latest ?? '') < expected) || stepFailed,
      steps
    }
  };
}

// ---- Cloudflare Access の証明(Cf-Access-Jwt-Assertion)----

const b64url = (text) => Uint8Array.from(atob(text.replace(/-/g, '+').replace(/_/g, '/')), (c) => c.charCodeAt(0));
const decodeJson = (text) => JSON.parse(new TextDecoder().decode(b64url(text)));

/**
 * Access の証明を確かめる。チームと AUD が設定されていなければ通さない(守りの側に倒す)。
 * getKeys(team) は、チームの公開鍵(JWK の配列)を返す関数。
 */
export async function verifyAccess(token, env, getKeys, nowSeconds = Math.floor(Date.now() / 1000)) {
  const team = env?.ACCESS_TEAM;
  const aud = env?.ACCESS_AUD;
  if (!team || !aud || !token) return false;
  const parts = token.split('.');
  if (parts.length !== 3) return false;
  let header;
  let payload;
  try {
    header = decodeJson(parts[0]);
    payload = decodeJson(parts[1]);
  } catch {
    return false;
  }
  if (header.alg !== 'RS256') return false;
  const audiences = Array.isArray(payload.aud) ? payload.aud : [payload.aud];
  if (!audiences.includes(aud)) return false;
  if (payload.iss !== `https://${team}.cloudflareaccess.com`) return false;
  if (typeof payload.exp !== 'number' || payload.exp <= nowSeconds) return false;
  const keys = await getKeys(team);
  const jwk = keys.find((k) => k.kid === header.kid);
  if (!jwk) return false;
  const key = await crypto.subtle.importKey('jwk', jwk, { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['verify']);
  return crypto.subtle.verify('RSASSA-PKCS1-v1_5', key, b64url(parts[2]), new TextEncoder().encode(`${parts[0]}.${parts[1]}`));
}
