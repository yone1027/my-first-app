<script lang="ts">
  /** G-21 週次 手法ごとの判定表(基本設計書 §5.4)。 */
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import Cautions from '$lib/components/Cautions.svelte';
  import CardState from '$lib/components/CardState.svelte';
  import Tag from '$lib/components/Tag.svelte';
  import WeeklyTabs from '$lib/components/WeeklyTabs.svelte';
  import { api, ApiFailure, type Dates, type MethodResult, type VerdictDetail, type Verdicts } from '$lib/api';
  import { oku } from '$lib/format';
  import { SEGMENT_LABEL, tradingViewUrl, VERDICT_LABEL } from '$lib/labels';
  import { BUY_COUNTS, compare, DEFAULT_FILTERS, filter, PAGE_SIZE, sortKey, type Filters } from '$lib/verdicts';

  const wanted = $derived(page.url.searchParams.get('date') ?? 'latest');
  const wantedCode = $derived(page.url.searchParams.get('code'));

  let dates = $state<Dates | null>(null);
  let data = $state<Verdicts | null>(null);
  let failure = $state<string | null>(null);
  let filters = $state<Filters>({ ...DEFAULT_FILTERS });
  let pageNo = $state(1);
  let openCode = $state<string | null>(null);
  let detail = $state<VerdictDetail | null>(null);
  let detailMethod = $state<string>('granville');

  $effect(() => {
    api.dates().then((d) => (dates = d)).catch(() => (dates = null));
  });

  $effect(() => {
    const want = wanted;
    api
      .verdicts(want)
      .then((body) => {
        data = body;
        failure = null;
        pageNo = 1;
      })
      .catch((e: ApiFailure) => {
        data = null;
        if (e.body?.error === 'no_such_date' && e.body.latest) {
          failure = '指定した基準日のデータはありません。最新の基準日で開きます';
          goto(`/weekly/verdicts?date=${e.body.latest}`, { replaceState: true });
        } else {
          failure = e.body?.error === 'no_data' ? 'この週のデータはありません' : `読み込みに失敗しました(${e.status})`;
        }
      });
  });

  // 検索から来たとき: 絞り込みを既定にし、その行を開く(§8.6 の 4)
  $effect(() => {
    const code = wantedCode;
    if (!code || !data) return;
    filters = { ...DEFAULT_FILTERS, capMin: null };
    const at = sorted.findIndex((r) => r.code === code);
    if (at >= 0) {
      pageNo = Math.floor(at / PAGE_SIZE) + 1;
      open(code);
    }
  });

  // 並べ替えのキーは基準日のデータを受け取ったときに1回だけ作る(§8.6)
  const keys = $derived.by(() => {
    const map = new Map<string, number[]>();
    for (const row of data?.rows ?? []) map.set(row.code, sortKey(row));
    return map;
  });
  const sorted = $derived(
    [...(data?.rows ?? [])].sort((a, b) => compare(keys.get(a.code) ?? [], keys.get(b.code) ?? []))
  );
  const shown = $derived(filter(sorted, filters));
  const pages = $derived(Math.max(1, Math.ceil(shown.length / PAGE_SIZE)));
  const slice = $derived(shown.slice((pageNo - 1) * PAGE_SIZE, pageNo * PAGE_SIZE));
  const phaseChoices = $derived(filters.method ? (data?.phases[filters.method] ?? []) : []);

  async function open(code: string) {
    if (openCode === code) {
      openCode = null;
      detail = null;
      return;
    }
    openCode = code;
    detail = null;
    detailMethod = filters.method || 'granville';
    try {
      detail = await api.verdictDetail(data!.date, code);
    } catch {
      detail = null;
    }
  }

  function reset() {
    filters = { ...DEFAULT_FILTERS };
    pageNo = 1;
  }

  /** フラッグ/ペナントは2つの結果を並べる(§5.4)。 */
  function parts(result: MethodResult | Record<string, MethodResult>): [string, MethodResult][] {
    if (result && 'verdict' in result) return [['', result as MethodResult]];
    return Object.entries(result as Record<string, MethodResult>);
  }
</script>

<WeeklyTabs {dates} date={data?.date ?? ''} tab="verdicts" counts={{ verdicts: data?.rows.length ?? null }} />
<CardState error={failure} />

{#if data}
  <div class="card">
    <p class="sub" style="margin-top: 0">
      TechnicalAnalysis の一括分析(土曜 3:00 に自動実行)。対象は基準日時点の {data.universe_count} 銘柄。
    </p>
    <Cautions />
  </div>

  <!-- (2) 絞り込み -->
  <section class="card">
    <h2>絞り込み</h2>
    <div class="row" style="margin-bottom: 10px">
      <span class="muted" style="min-width: 120px">買い判定の数(以上)</span>
      {#each BUY_COUNTS as c}
        <button type="button" aria-pressed={filters.buyCount === c.value} onclick={() => { filters.buyCount = c.value; pageNo = 1; }}>
          {c.label}
        </button>
      {/each}
    </div>
    <div class="row">
      <label>手法
        <select bind:value={filters.method} onchange={() => { filters.verdict = ''; filters.phases = []; pageNo = 1; }}>
          <option value="">すべて</option>
          {#each data.methods as m}<option value={m.key}>{m.label}</option>{/each}
        </select>
      </label>
      <label>判定
        <select bind:value={filters.verdict} disabled={!filters.method} onchange={() => (pageNo = 1)}>
          <option value="">すべて</option>
          {#each ['buy', 'neutral', 'sell', 'unknown', 'conflict'] as v}<option value={v}>{VERDICT_LABEL[v]}</option>{/each}
        </select>
      </label>
      <label>局面
        <select multiple bind:value={filters.phases} disabled={!filters.method} size="1" onchange={() => (pageNo = 1)}>
          {#each phaseChoices as p}<option value={p}>{p}</option>{/each}
        </select>
      </label>
      <label>市場
        <select bind:value={filters.market} onchange={() => (pageNo = 1)}>
          <option value="">すべて</option>
          {#each ['prime', 'standard', 'growth'] as m}<option value={m}>{SEGMENT_LABEL[m]}</option>{/each}
        </select>
      </label>
      <label>業種
        <select bind:value={filters.s33} onchange={() => (pageNo = 1)}>
          <option value="">すべて</option>
          {#each data.sectors as s}<option value={s.s33}>{s.name}</option>{/each}
        </select>
      </label>
      <label>時価総額(億円)
        <input type="number" inputmode="numeric" placeholder="下限" bind:value={filters.capMin} onchange={() => (pageNo = 1)} style="width: 100px" />
        〜
        <input type="number" inputmode="numeric" placeholder="上限なし" bind:value={filters.capMax} onchange={() => (pageNo = 1)} style="width: 100px" />
      </label>
      <button type="button" onclick={reset}>条件をクリア</button>
      <div class="grow"></div>
      <strong>該当 {shown.length} 銘柄 / {data.rows.length}</strong>
    </div>
    <p class="muted">買い判定の数は絞り込みのためだけに数える。列や点数としては出さない。</p>
  </section>

  <!-- (3) 判定表 -->
  <section class="card">
    <div class="scroll-x">
      <table>
        <thead>
          <tr>
            <th>コード</th>
            <th>銘柄名</th>
            <th>市場</th>
            <th class="num">時価総額(億円)</th>
            {#each data.methods as m}<th>{m.label}{#if m.timeframe}<span class="muted">({m.timeframe})</span>{/if}</th>{/each}
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each slice as row}
            <tr>
              <td>{row.code}</td>
              <td><a href={tradingViewUrl(row.code)} target="_blank" rel="noopener noreferrer">{row.name}</a></td>
              <td>{SEGMENT_LABEL[row.market] ?? row.market}</td>
              <td class="num">{oku(row.market_cap_oku)}</td>
              {#each data.methods as m}
                <td>
                  <Tag verdict={row.v[m.key]?.[0]} />
                  <div class="muted phase">{row.v[m.key]?.[1] ?? ''}</div>
                </td>
              {/each}
              <td>
                <button type="button" onclick={() => open(row.code)} aria-expanded={openCode === row.code}>
                  {openCode === row.code ? '閉じる' : '根拠'}
                </button>
              </td>
            </tr>
            {#if openCode === row.code}
              <tr class="detail">
                <td colspan={5 + data.methods.length}>
                  {#if !detail}
                    <p class="muted">読み込み中…</p>
                  {:else}
                    <div class="row" style="gap: 4px; margin-bottom: 8px">
                      {#each data.methods as m}
                        {#if detail.methods[m.key]}
                          <button type="button" aria-pressed={detailMethod === m.key} onclick={() => (detailMethod = m.key)}>{m.label}</button>
                        {/if}
                      {/each}
                    </div>
                    {#if detail.methods[detailMethod]}
                      {#each parts(detail.methods[detailMethod]) as [name, result]}
                        <div class="part">
                          {#if name}<h3>{name}</h3>{/if}
                          <p>
                            <Tag verdict={result.verdict} /> {result.phase_label ?? ''}
                            <span class="muted">({result.timeframe ?? ''})</span>
                          </p>
                          {#each result.signals as sig}
                            <div class="signal">
                              <div><strong>{sig.date}</strong> <Tag verdict={sig.direction} /> {sig.name}</div>
                              <div class="muted">典拠: {sig.basis}{#if sig.provisional}(仮置き){/if}</div>
                              {#each sig.evidence as ev}
                                <div class="muted">
                                  {ev.label ?? ''}{#if ev.date} / {ev.date}{/if}
                                  {#if ev.values}
                                    {#each Object.entries(ev.values) as [k, v]}<span class="kv">{k}={v}</span>{/each}
                                  {/if}
                                </div>
                              {/each}
                            </div>
                          {/each}
                          {#if result.notes.length}
                            <ul class="muted">{#each result.notes as note}<li>{note}</li>{/each}</ul>
                          {/if}
                        </div>
                      {/each}
                    {/if}
                    <p><a href={tradingViewUrl(row.code)} target="_blank" rel="noopener noreferrer">TradingView で開く ›</a></p>
                  {/if}
                </td>
              </tr>
            {/if}
          {/each}
        </tbody>
      </table>
    </div>

    <div class="row" style="margin-top: 10px">
      <span class="muted">
        {shown.length === 0 ? 0 : (pageNo - 1) * PAGE_SIZE + 1}〜{Math.min(pageNo * PAGE_SIZE, shown.length)} / {shown.length} 銘柄を表示
      </span>
      <div class="grow"></div>
      <button type="button" onclick={() => (pageNo = Math.max(1, pageNo - 1))} disabled={pageNo <= 1}>前へ</button>
      <span>{pageNo} / {pages}</span>
      <button type="button" onclick={() => (pageNo = Math.min(pages, pageNo + 1))} disabled={pageNo >= pages}>次へ</button>
    </div>
    <p class="muted">
      並び順: グランビル → 決算ブレイクアウト → フラッグ/ペナント → ボリンジャーバンド → MACD の判定の順
      (各手法の中は 買い → 中立 → 判定不能 → 売り。食い違いは判定不能と同じ位置)、最後に時価総額の大きい順。
    </p>
  </section>

  {#if data.failed.length}
    <section class="card">
      <h2>失敗した銘柄: {data.failed.length}件</h2>
      <ul class="muted">
        {#each data.failed as f}<li>{f.code} {f.name ?? ''} — {f.reason ?? ''}</li>{/each}
      </ul>
    </section>
  {/if}
{/if}

<style>
  label { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; color: var(--text-sub); }
  .phase { font-size: 11px; max-width: 200px; white-space: normal; }
  tr.detail td { background: var(--surface-alt); white-space: normal; }
  .part { margin-bottom: 12px; }
  .signal { border-left: 2px solid var(--border-strong); padding-left: 8px; margin: 6px 0; }
  .kv { margin-right: 8px; font-variant-numeric: tabular-nums; }
</style>
