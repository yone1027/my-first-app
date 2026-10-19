/**
 * /api/* を受ける Pages Functions(詳細設計書 §13.4)。
 * 受け付けるのは GET だけ。Access の証明が無い要求には何も返さない(403)。
 */

import { computeStatus, pickDetail, resolveWeekly, route, search, SEARCH_MAX_LENGTH, verifyAccess } from '../../lib/portal.js';

const HEADERS = {
  'content-type': 'application/json; charset=utf-8',
  'x-robots-tag': 'noindex',
  'cache-control': 'private, no-store'
};

const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: HEADERS });

// チームの公開鍵は数時間ごとに入れ替わることがあるので、1時間だけ覚えておく
let certs = { team: null, keys: [], at: 0 };
async function getKeys(team) {
  if (certs.team === team && Date.now() - certs.at < 3600_000) return certs.keys;
  const response = await fetch(`https://${team}.cloudflareaccess.com/cdn-cgi/access/certs`);
  const keys = response.ok ? (await response.json()).keys ?? [] : [];
  certs = { team, keys, at: Date.now() };
  return keys;
}

/** 手元で `wrangler pages dev` を動かすときだけ、Access を外せる(localhost のときに限る)。 */
function devBypass(request, env) {
  const host = new URL(request.url).hostname;
  return env.ACCESS_DEV_BYPASS === '1' && (host === 'localhost' || host === '127.0.0.1');
}

/** 書き出した JSON を読む。無ければ null(SPA の index.html が返ってきたときも無いとみなす)。 */
async function asset(env, request, key) {
  const response = await env.ASSETS.fetch(new URL(`/_data/${key}`, request.url));
  const type = response.headers.get('content-type') ?? '';
  if (!response.ok || !type.includes('json')) return null;
  return response;
}

async function readJson(env, request, key) {
  const response = await asset(env, request, key);
  return response ? response.json() : null;
}

export async function onRequest(context) {
  const { request, env, params } = context;
  if (request.method !== 'GET' && request.method !== 'HEAD') return json({ error: 'method_not_allowed' }, 405);

  if (!devBypass(request, env)) {
    let ok = false;
    try {
      ok = await verifyAccess(request.headers.get('cf-access-jwt-assertion'), env, getKeys);
    } catch {
      ok = false;
    }
    if (!ok) return json({ error: 'forbidden' }, 403);
  }

  const url = new URL(request.url);
  const path = [].concat(params.path ?? []).join('/');
  let found = route(path, url.searchParams);

  if (found.kind === 'health') return json({ ok: true });
  if (found.kind === 'status') {
    const base = await readJson(env, request, 'status_base.json');
    return base ? json(computeStatus(base, new Date())) : json({ error: 'not_built' }, 503);
  }
  if (found.kind === 'search') {
    const q = url.searchParams.get('q') ?? '';
    if (q.length > SEARCH_MAX_LENGTH) return json({ error: 'bad_request' }, 422);
    const index = await readJson(env, request, 'search.json');
    return json(index ? search(index, q) : []);
  }
  if (found.kind === 'weekly') {
    found = resolveWeekly(found, await readJson(env, request, 'weekly/dates.json'));
  }
  if (found.kind === 'error') return json(found.body, found.status);
  if (found.kind === 'detail') {
    const picked = pickDetail(await readJson(env, request, found.key), found.code);
    return json(picked.body, picked.status);
  }

  // そのまま返す。書き出したときに 404 などだった応答は、その状態で返す
  const response = await asset(env, request, found.key);
  if (!response) return json({ error: 'no_data', detail: found.key }, 404);
  const errors = (await readJson(env, request, 'errors.json')) ?? {};
  return new Response(response.body, { status: errors[found.key] ?? 200, headers: HEADERS });
}
