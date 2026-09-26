/** API の呼び出し(詳細設計書 §5)。受け付けるのは GET だけ。 */

export type ApiError = { error: string; detail?: string; latest?: string; file?: string };

export class ApiFailure extends Error {
  constructor(
    readonly status: number,
    readonly body: ApiError
  ) {
    super(`${status} ${body.error}`);
  }
}

async function get<T>(path: string, fetcher: typeof fetch = fetch): Promise<T> {
  const response = await fetcher(path, { headers: { accept: 'application/json' } });
  if (!response.ok) {
    let body: ApiError = { error: 'unknown' };
    try {
      body = (await response.json()) as ApiError;
    } catch {
      /* 本文が無い応答(403 など) */
    }
    throw new ApiFailure(response.status, body);
  }
  return (await response.json()) as T;
}

/** 失敗しても画面を止めない読み込み。カードごとの部分失敗に使う(§8.2)。 */
export async function tryGet<T>(path: string, fetcher: typeof fetch = fetch): Promise<{ data: T | null; error: ApiFailure | null }> {
  try {
    return { data: await get<T>(path, fetcher), error: null };
  } catch (error) {
    return { data: null, error: error instanceof ApiFailure ? error : new ApiFailure(0, { error: 'network' }) };
  }
}

export const api = {
  status: (f?: typeof fetch) => get<Status>('/api/status', f),
  theme: (f?: typeof fetch) => get<Record<string, string | string[]>>('/api/theme', f),
  japan: (period: string, f?: typeof fetch) => get<Japan>(`/api/market/japan?period=${period}`, f),
  segments: (period: string, f?: typeof fetch) => get<Segments>(`/api/market/segments?period=${period}`, f),
  sectors: (period: string, scope: string, f?: typeof fetch) =>
    get<Sectors>(`/api/market/sectors?period=${period}&scope=${scope}`, f),
  dates: (f?: typeof fetch) => get<Dates>('/api/weekly/dates', f),
  verdicts: (date: string, f?: typeof fetch) => get<Verdicts>(`/api/weekly/${date}/verdicts`, f),
  verdictDetail: (date: string, code: string, f?: typeof fetch) =>
    get<VerdictDetail>(`/api/weekly/${date}/verdicts/${code}`, f),
  picks: (date: string, f?: typeof fetch) => get<Picks>(`/api/weekly/${date}/picks`, f),
  candidates: (date: string, f?: typeof fetch) => get<Candidates>(`/api/weekly/${date}/candidates`, f),
  search: (q: string, f?: typeof fetch) => get<SearchHit[]>(`/api/search?q=${encodeURIComponent(q)}`, f)
};

// ---- 応答の形(§5.3・§5.4)----

export type Week = { start: string | null; end: string; days: number | null; short: boolean | null };
export type Params = { period: string; weeks: number; recent: number; scope?: string };

export type Status = {
  now: string;
  expected_week_end: string | null;
  delayed_after: string;
  market: { data_week_end: string | null; last_updated: string | null; delayed: boolean };
  weekly: {
    latest_date: string | null;
    last_updated: string | null;
    delayed: boolean;
    steps: Record<string, string>;
  };
};

export type Series = (number | null)[];

export type Japan = {
  params: Params;
  as_of_week: { start: string | null; end: string | null };
  weeks: Week[];
  turnover: { latest: number | null; avg13: number | null; ratio13: number | null; percentile: number | null; series: Series; ma13: Series };
  topix: { close: Series; ma13: Series; ma26: Series; ma52: Series };
  allocation: { segment: string; share_latest: number | null; share_change_pt: number | null }[];
  investors: Investors;
  valuation: {
    per: Series; eps: Series; n_target: number | null; n_excluded_loss: number | null;
    per_change: number | null; per_change_pct: number | null; eps_change_pct: number | null; topix_change_pct: number | null;
  };
  indicators: { key: string; values: Series; latest: number | null; change: number | null; last_obs: string | null; not_built: string | null }[];
  manifest: { generated_at: string | null; latest_week_end: string | null };
};

export type Investors = {
  section: string;
  latest_published: { end: string; pub_date: string | null } | null;
  subjects: { key: string; series: Series; total: number | null; avg_recent: number | null; avg_period: number | null }[];
  summary: { up: string[]; down: string[] } | null;
  not_built?: string | null;
};

export type Segments = {
  params: Params;
  weeks: Week[];
  segments: {
    segment: string; share: Series; share_latest: number | null; share_avg_period: number | null;
    share_avg_recent: number | null; period_average_ratio: number | null; turnover: Series;
    per: Series; np_sum: Series; n_target: number | null; np_change_pct: number | null; investors: Investors;
  }[];
};

export type Sectors = {
  params: Params;
  weeks: Week[];
  summary: { up: { s33: string; name: string; ratio: number }[]; down: { s33: string; name: string; ratio: number }[] };
  sectors: {
    s33: string; name: string; share_latest: number | null; share_avg_period: number | null;
    period_average_ratio: number | null; emphasis: 'top' | 'bottom' | null; heat: Series;
  }[];
};

export type Dates = {
  latest: string | null;
  dates: { date: string; weekday: string; has: { verdicts: boolean; picks: boolean; candidates: boolean } }[];
};

export type VerdictCode = 'buy' | 'neutral' | 'sell' | 'unknown' | 'conflict';
export type VerdictRow = {
  code: string; name: string; market: string; s33: string; market_cap_oku: number | null;
  v: Record<string, [VerdictCode | null, string | null]>;
};
export type Verdicts = {
  date: string;
  methods: { key: string; label: string; timeframe: string | null }[];
  universe_count: number;
  sectors: { s33: string; name: string }[];
  phases: Record<string, string[]>;
  rows: VerdictRow[];
  failed: { code: string; name: string | null; reason: string | null }[];
};

export type Signal = {
  date: string | null; direction: string | null; name: string | null;
  basis: string; provisional: boolean;
  evidence: { label?: string; date?: string; values?: Record<string, number> }[];
};
export type MethodResult = {
  verdict: string | null; phase_label: string | null; timeframe: string | null;
  signals: Signal[]; notes: string[];
};
export type VerdictDetail = {
  code: string; name: string | null;
  methods: Record<string, MethodResult | Record<string, MethodResult>>;
};

export type Pick = {
  rank: number | null; code: string; name: string; sector_name: string | null;
  close: number | null; entry: number | null; stop: number | null; target: number | null;
  rr: number | null; confluence: number | null; confluence_names: string | null;
  p_fill: number | null; p_target: number | null; p_stop: number | null; p_time: number | null;
  ev_fill: number | null; ev_order: number | null;
  ladder: Record<string, string | number | null>[];
};
export type Picks = {
  date: string;
  header: {
    validity: { start?: string; end?: string; text?: string } | null;
    validity_calendar?: { start: string; end: string; days: number };
    settlement: string | null; universe: number | null; plans: number | null;
    criteria_badges: string[]; model: string | null;
  };
  picks: Pick[];
  reference: Record<string, string | number | null>[];
  limits: { bullets: string[]; table: Record<string, string | number | null>[] };
};

export type Candidate = {
  rank: number; code: string; name: string; s33: string; market_cap_oku: number | null;
  method: string; method_filter: string | null; level: string; formed_on: string;
  entry: number | null; stop_line: string; stop: number | null;
  hold_pct: number | null; touches: number | null;
  risk_pct: number | null; reward_pct: number | null; rr: number | null;
};
export type Candidates = {
  date: string;
  method_filters: { key: string; label: string }[];
  rows: Candidate[];
};

export type SearchHit = { code: string; name: string; market: string; in_universe: boolean };
