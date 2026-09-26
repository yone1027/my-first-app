<script lang="ts">
  /** G-22 週次 来週の買い注文の候補(基本設計書 §5.5)。 */
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import Cautions from '$lib/components/Cautions.svelte';
  import CardState from '$lib/components/CardState.svelte';
  import WeeklyTabs from '$lib/components/WeeklyTabs.svelte';
  import { api, ApiFailure, type Dates, type Picks } from '$lib/api';
  import { dec, int, pct, price, ratioPct } from '$lib/format';
  import { tradingViewUrl } from '$lib/labels';
  import { loadCapital, saveCapital, shares } from '$lib/shares';

  const wanted = $derived(page.url.searchParams.get('date') ?? 'latest');
  let dates = $state<Dates | null>(null);
  let data = $state<Picks | null>(null);
  let failure = $state<string | null>(null);
  let capital = $state<number | null>(null);

  onMount(() => {
    capital = loadCapital();
  });

  $effect(() => {
    api.dates().then((d) => (dates = d)).catch(() => (dates = null));
  });

  $effect(() => {
    const want = wanted;
    api
      .picks(want)
      .then((body) => {
        data = body;
        failure = null;
      })
      .catch((e: ApiFailure) => {
        data = null;
        if (e.body?.error === 'no_such_date' && e.body.latest) {
          goto(`/weekly/picks?date=${e.body.latest}`, { replaceState: true });
        } else {
          failure = e.body?.error === 'no_data' ? 'この週のデータはありません' : `読み込みに失敗しました(${e.status})`;
        }
      });
  });

  function onCapital(value: number | null) {
    capital = value;
    saveCapital(value);
  }

  const columns = (rows: Record<string, unknown>[]) => (rows.length ? Object.keys(rows[0]) : []);

  /** md の「注文の有効期間: …」の行から、見出しの重複を取る。 */
  function validityText(v: { start?: string; end?: string; text?: string }): string {
    const text = v.text ?? (v.start && v.end ? `${v.start}〜${v.end}` : '');
    return text.replace(/^注文の有効期間:\s*/, '');
  }

  /** Markdown の表を読むときに % を外して数にしているので、表示で付け直す(§7.2)。 */
  const PERCENT_COLUMNS = new Set([
    '終値から', '下がる確率', '約定後の損切り確率', '約定時の期待', '注文の期待',
    '約定確率', '損切り確率', '平均リターン', '同じ期間の TOPIX', '超過',
    '予測の損切り確率', '実際の損切り率', '予測の目標到達確率', '実際の目標到達率'
  ]);

  function cellText(column: string, value: unknown): string {
    if (value == null || value === '') return '—';
    if (typeof value === 'number' && PERCENT_COLUMNS.has(column)) {
      return `${value.toLocaleString('ja-JP')}%`.replace('-', '−');
    }
    if (typeof value === 'number') return value.toLocaleString('ja-JP').replace('-', '−');
    return String(value);
  }
</script>

<WeeklyTabs {dates} date={data?.date ?? ''} tab="picks" counts={{ picks: data?.picks.length ?? null }} />
<CardState error={failure} />

{#if data}
  <section class="card">
    <h2>注文の前提</h2>
    {#if data.header.validity}
      <p><strong>注文の有効期間:</strong> {validityText(data.header.validity)}</p>
    {/if}
    {#if data.header.validity_calendar}
      <p class="notice notice--warn">
        取引カレンダーでは {data.header.validity_calendar.start}〜{data.header.validity_calendar.end} です。
        表示は分析の出力(md)に合わせています。
      </p>
    {/if}
    {#if data.header.settlement}<p><strong>決済:</strong> {data.header.settlement}</p>{/if}
    <p class="sub">
      前提を満たした銘柄 {int(data.header.universe)} / 計画 {int(data.header.plans)} 件
    </p>
    <div class="row" style="gap: 6px">
      {#each data.header.criteria_badges as badge}<span class="badge">{badge}</span>{/each}
    </div>
    {#if data.header.model}<p class="muted">{data.header.model}</p>{/if}
    <Cautions />
  </section>

  {#if data.picks.length === 0}
    <section class="card"><h2>今週は見送り</h2><p class="sub">基準を満たす候補がありませんでした。件数を揃えるために基準は緩めません。</p></section>
  {/if}

  {#each data.picks as p}
    <section class="card">
      <h2>{p.rank ?? ''}. {p.code} {p.name}{#if p.sector_name}<span class="muted">({p.sector_name})</span>{/if}</h2>
      <div class="scroll-x">
        <table>
          <tbody>
            <tr><th>基準日の終値</th><td class="num">{price(p.close)} 円</td></tr>
            <tr><th>買いの指値(この値段まで下がったら買う)</th><td class="num"><strong>{price(p.entry)} 円</strong>({p.close && p.entry ? pct((p.entry / p.close - 1) * 100, 1, true) : '—'})</td></tr>
            <tr><th>損切り(逆指値)</th><td class="num">{price(p.stop)} 円({p.entry && p.stop ? pct((p.stop / p.entry - 1) * 100, 1, true) : '—'})</td></tr>
            <tr><th>目標(指値売り)</th><td class="num">{price(p.target)} 円({p.entry && p.target ? pct((p.target / p.entry - 1) * 100, 1, true) : '—'})</td></tr>
            <tr><th>リワード ÷ リスク</th><td class="num">{dec(p.rr, 2)}</td></tr>
            <tr><th>指値の根拠(重なる支持線 {int(p.confluence)} 本)</th><td>{p.confluence_names ?? '—'}</td></tr>
            <tr><th>翌週この指値まで下がる確率</th><td class="num">{ratioPct(p.p_fill)}</td></tr>
            <tr><th>約定後: 目標到達 / 損切り / 期限</th><td class="num">{ratioPct(p.p_target)} / {ratioPct(p.p_stop)} / {ratioPct(p.p_time)}</td></tr>
            <tr><th>約定したときの期待リターン</th><td class="num">{ratioPct(p.ev_fill)}</td></tr>
            <tr><th>注文1件あたりの期待リターン(買えない場合の0を含む)</th><td class="num">{ratioPct(p.ev_order)}</td></tr>
          </tbody>
        </table>
      </div>

      {#if p.ladder.length}
        <h3>同じ銘柄の指値の段</h3>
        <p class="muted">来週どこまで下がりそうか。各段で期待値が最大の損切り・目標の組み合わせ。</p>
        <div class="scroll-x">
          <table>
            <thead><tr>{#each columns(p.ladder) as c}<th class:num={c !== '支持線'}>{c}</th>{/each}</tr></thead>
            <tbody>
              {#each p.ladder as step}
                <tr>{#each columns(p.ladder) as c}<td class:num={c !== '支持線'}>{cellText(c, step[c])}</td>{/each}</tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}

      <h3>株数の目安</h3>
      <div class="row">
        <label>投資資金(円)
          <input
            type="text"
            inputmode="numeric"
            value={capital ? capital.toLocaleString('ja-JP') : ''}
            oninput={(e) => {
              const digits = (e.currentTarget as HTMLInputElement).value.replace(/[^\d]/g, '');
              onCapital(digits ? Number(digits) : null);
            }}
            style="width: 140px"
          />
        </label>
        {#if capital}
          {@const s = shares(capital, p.entry, p.stop)}
          <span>
            1回のリスク上限(資金の5%){int(s.riskLimit)} 円 ÷ 指値と損切りの差 {int(s.perShare)} 円 =
            {#if s.unitShares === 0}
              <strong>0 株(資金が足りません)</strong>
            {:else}
              <strong>{int(s.shares)} 株</strong> → 単元(100株)で <strong>{int(s.unitShares)} 株</strong>
            {/if}
          </span>
        {/if}
      </div>
      <p class="muted">同じ週に複数買う場合は、合計のリスクも資金の5%以内に抑える。入力した資金はこの端末に保存されます。</p>
      <p><a href={tradingViewUrl(p.code)} target="_blank" rel="noopener noreferrer">TradingView で開く ›</a></p>
    </section>
  {/each}

  {#if data.reference.length}
    <section class="card">
      <h2>参考: 期待値の上位の銘柄と、基準で落ちた理由</h2>
      <div class="scroll-x">
        <table>
          <thead><tr>{#each columns(data.reference) as c}<th>{c}</th>{/each}</tr></thead>
          <tbody>
            {#each data.reference as r}<tr>{#each columns(data.reference) as c}<td class:num={typeof r[c] === 'number'}>{cellText(c, r[c])}</td>{/each}</tr>{/each}
          </tbody>
        </table>
      </div>
    </section>
  {/if}

  {#if data.limits.bullets.length || data.limits.table.length}
    <section class="card">
      <h2>この数値の読み方(検証で分かっている限界)</h2>
      <ul>{#each data.limits.bullets as line}<li>{line}</li>{/each}</ul>
      {#if data.limits.table.length}
        <div class="scroll-x">
          <table>
            <thead><tr>{#each columns(data.limits.table) as c}<th>{c}</th>{/each}</tr></thead>
            <tbody>
              {#each data.limits.table as r}<tr>{#each columns(data.limits.table) as c}<td class:num={typeof r[c] === 'number'}>{cellText(c, r[c])}</td>{/each}</tr>{/each}
            </tbody>
          </table>
        </div>
      {/if}
    </section>
  {/if}
{/if}

<style>
  .badge { background: var(--surface-alt); border: 1px solid var(--border-strong); border-radius: 999px; padding: 3px 10px; font-size: 12px; }
  label { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; color: var(--text-sub); }
  th { white-space: normal; }
</style>
