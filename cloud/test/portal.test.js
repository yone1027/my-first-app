// クラウド版の API(詳細設計書 §11.4)。`npm test` で動かす。
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { computeStatus, pickDetail, resolveWeekly, route, search, verifyAccess } from '../lib/portal.js';

const params = (q) => new URLSearchParams(q);

test('market の period と scope は許可リストで直す(不正なら既定値)', () => {
  assert.deepEqual(route('market/japan', params('period=26w')), { kind: 'file', key: 'market/japan.26w.json' });
  assert.deepEqual(route('market/segments', params('period=99w')), { kind: 'file', key: 'market/segments.13w.json' });
  assert.deepEqual(route('market/sectors', params('period=52w&scope=growth')), { kind: 'file', key: 'market/sectors.52w.growth.json' });
  assert.deepEqual(route('market/sectors', params('scope=x')), { kind: 'file', key: 'market/sectors.13w.all.json' });
});

test('知らない URL は 404', () => {
  assert.equal(route('market/unknown', params('')).status, 404);
  assert.equal(route('../theme', params('')).status, 404);
  assert.equal(route('weekly/2026-10-16/verdicts/7203/x', params('')).status, 404);
});

const dates = { dates: [{ date: '2026-10-16' }, { date: '2026-10-09' }], latest: '2026-10-16' };

test('latest は最新の基準日に直し、無い日は no_such_date', () => {
  const latest = resolveWeekly(route('weekly/latest/picks', params('')), dates);
  assert.deepEqual(latest, { kind: 'file', key: 'weekly/2026-10-16/picks.json' });
  const missing = resolveWeekly(route('weekly/2026-01-02/picks', params('')), dates);
  assert.deepEqual(missing, { kind: 'error', status: 404, body: { error: 'no_such_date', latest: '2026-10-16' } });
  assert.equal(resolveWeekly(route('weekly/latest/picks', params('')), { dates: [] }).body.error, 'no_data');
});

test('根拠はコードの先頭2文字のファイルから取り出す', () => {
  const found = resolveWeekly(route('weekly/2026-10-09/verdicts/285A', params('')), dates);
  assert.deepEqual(found, { kind: 'detail', key: 'weekly/2026-10-09/detail/28.json', code: '285A' });
  assert.deepEqual(pickDetail({ '285A': { code: '285A' } }, '285A'), { status: 200, body: { code: '285A' } });
  assert.equal(pickDetail({}, '9999').status, 404);
});

const index = {
  rows: [
    { code: '7203', name: 'トヨタ自動車', name_key: 'トヨタ自動車', market: 'prime' },
    { code: '7205', name: '日野自動車', name_key: '日野自動車', market: 'prime' },
    { code: '4443', name: 'Sansan', name_key: 'SANSAN', market: 'prime' },
    { code: '9861', name: '吉野家ホールディングス', name_key: '吉野家ホールディングス', market: 'prime' }
  ],
  universe: ['7203', '9861']
};

test('検索: コードの前方一致を先に、名前は出てくる位置の順', () => {
  assert.deepEqual(search(index, '7203').map((r) => r.code), ['7203']);
  assert.deepEqual(search(index, '72030').map((r) => r.code), ['7203']);
  assert.deepEqual(search(index, '自動車').map((r) => r.code), ['7205', '7203']);
  assert.deepEqual(search(index, 'ｓａｎｓａｎ')[0], { code: '4443', name: 'Sansan', market: 'prime', in_universe: false });
  assert.equal(search(index, '吉野家')[0].in_universe, true);
  assert.deepEqual(search(index, '  '), []);
});

const base = {
  delayed_after: 'SAT 12:00',
  schedule: { weekday: 5, at: '12:00' },
  cutoff: '17:00',
  market: { data_week_end: '2026-10-16', last_updated: 'x' },
  weekly: { latest_date: '2026-10-16', last_updated: 'y', steps: { candidates: 'ok' } },
  week_ends: ['2026-10-09', '2026-10-16', '2026-10-23', '2026-10-30']
};
const at = (jst) => new Date(`${jst}+09:00`);

test('遅れ: 最終営業日の 17:00 を過ぎた週が期待する週。土曜 12:00 を過ぎても前の週なら遅れ', () => {
  const friday = computeStatus(base, at('2026-10-23T16:59:00'));
  assert.equal(friday.expected_week_end, '2026-10-16');
  assert.equal(friday.weekly.delayed, false);
  const evening = computeStatus(base, at('2026-10-23T17:00:00'));
  assert.equal(evening.expected_week_end, '2026-10-23');
  assert.equal(evening.weekly.delayed, false); // 土曜 12:00 まではまだ
  const saturday = computeStatus(base, at('2026-10-24T12:00:00'));
  assert.equal(saturday.market.delayed, true);
  assert.equal(saturday.weekly.delayed, true);
  assert.equal(saturday.now, '2026-10-24T12:00:00+09:00');
});

test('遅れ: 手順が失敗していれば、時刻にかかわらず週次は遅れ', () => {
  const failed = { ...base, weekly: { ...base.weekly, steps: { publish: 'failed' } } };
  assert.equal(computeStatus(failed, at('2026-10-19T10:00:00')).weekly.delayed, true);
});

// ---- Access の証明 ----

const enc = (obj) => Buffer.from(JSON.stringify(obj)).toString('base64url');

async function signed(payload, header = { alg: 'RS256', kid: 'k1' }) {
  const pair = await crypto.subtle.generateKey(
    { name: 'RSASSA-PKCS1-v1_5', modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' },
    true,
    ['sign', 'verify']
  );
  const body = `${enc(header)}.${enc(payload)}`;
  const sig = await crypto.subtle.sign('RSASSA-PKCS1-v1_5', pair.privateKey, new TextEncoder().encode(body));
  const jwk = { ...(await crypto.subtle.exportKey('jwk', pair.publicKey)), kid: 'k1' };
  return { token: `${body}.${Buffer.from(sig).toString('base64url')}`, keys: async () => [jwk] };
}

const env = { ACCESS_TEAM: 'yone', ACCESS_AUD: 'aud-1' };
const good = { aud: ['aud-1'], iss: 'https://yone.cloudflareaccess.com', exp: 2_000_000_000 };

test('Access: 正しい証明だけを通す', async () => {
  const { token, keys } = await signed(good);
  assert.equal(await verifyAccess(token, env, keys, 1_900_000_000), true);
  assert.equal(await verifyAccess(token, env, keys, 2_000_000_001), false); // 期限切れ
  assert.equal(await verifyAccess(token, { ...env, ACCESS_AUD: 'other' }, keys, 1_900_000_000), false);
  assert.equal(await verifyAccess(token, { ...env, ACCESS_TEAM: 'other' }, keys, 1_900_000_000), false);
  const tampered = token.replace(/\.[^.]+\./, `.${enc({ ...good, aud: ['aud-1'], exp: 2_100_000_000 })}.`);
  assert.equal(await verifyAccess(tampered, env, keys, 1_900_000_000), false);
});

test('Access: 設定が無い、証明が無い、形が違うときは通さない', async () => {
  const { token, keys } = await signed(good);
  assert.equal(await verifyAccess(token, {}, keys), false);
  assert.equal(await verifyAccess(null, env, keys), false);
  assert.equal(await verifyAccess('a.b', env, keys), false);
  const hs = await signed(good, { alg: 'HS256', kid: 'k1' });
  assert.equal(await verifyAccess(hs.token, env, hs.keys, 1_900_000_000), false);
});
