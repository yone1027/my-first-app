<script lang="ts">
  /** G-23 週次 買い候補(パターン)(基本設計書 §5.6)。
   *  PC は最初から全件、スマホは12件(2026-09-26 確定)。 */
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import Cautions from '$lib/components/Cautions.svelte';
  import CardState from '$lib/components/CardState.svelte';
  import WeeklyTabs from '$lib/components/WeeklyTabs.svelte';
  import { api, ApiFailure, type Candidates, type Dates } from '$lib/api';
  import { dec, oku, pct, price } from '$lib/format';
  import { tradingViewUrl } from '$lib/labels';

  const MOBILE_FIRST = 12;

  const wanted = $derived(page.url.searchParams.get('date') ?? 'latest');
  let dates = $state<Dates | null>(null);
  let data = $state<Candidates | null>(null);
  let failure = $state<string | null>(null);
  let method = $state('');
  let showAll = $state(true);

  onMount(() => {
    // スマホは1行が縦に積まれて長くなるので、12件から始める
    showAll = window.innerWidth >= 768;
  });

  $effect(() => {
    api.dates().then((d) => (dates = d)).catch(() => (dates = null));
  });

  $effect(() => {
    const want = wanted;
    api
      .candidates(want)
      .then((body) => {
        data = body;
        failure = null;
      })
      .catch((e: ApiFailure) => {
        data = null;
        if (e.body?.error === 'no_such_date' && e.body.latest) {
          goto(`/weekly/candidates?date=${e.body.latest}`, { replaceState: true });
        } else {
          failure = e.body?.error === 'no_data' ? 'この週のデータはありません' : `読み込みに失敗しました(${e.status})`;
        }
      });
  });

  const filtered = $derived((data?.rows ?? []).filter((r) => !method || r.method_filter === method));
  const shown = $derived(showAll ? filtered : filtered.slice(0, MOBILE_FIRST));
  const stocks = $derived(new Set(filtered.map((r) => r.code)).size);
</script>

<WeeklyTabs {dates} date={data?.date ?? ''} tab="candidates" counts={{ candidates: data?.rows.length ?? null }} />
<CardState error={failure} />

{#if data}
  <section class="card">
    <h2>買い候補 {filtered.length} 件 / {stocks} 銘柄</h2>
    <p class="sub">
      選び方: 週足パーフェクトオーダー、直近1週の反発・上抜け、損切りは支持線の 0.5% 下、リワードは一律 +10%。
    </p>
    <Cautions extra={['リスクの小さい銘柄が上位に来やすい偏りがある。リスクリワードは期待値ではない']} />
    <div class="row" style="gap: 6px; margin-top: 10px">
      <span class="muted">手法</span>
      <button type="button" aria-pressed={method === ''} onclick={() => (method = '')}>すべて</button>
      {#each data.method_filters as f}
        <button type="button" aria-pressed={method === f.key} onclick={() => (method = f.key)}>{f.label}</button>
      {/each}
    </div>
  </section>

  <section class="card">
    <div class="scroll-x">
      <table>
        <thead>
          <tr>
            <th class="num">順位</th>
            <th>コード</th>
            <th>銘柄名</th>
            <th class="num">時価総額(億円)</th>
            <th>手法</th>
            <th>水準</th>
            <th class="num">想定の買値</th>
            <th>損切りの支持線</th>
            <th class="num">損切り価格</th>
            <th class="num">支持線の守った割合 / 触れた回数</th>
            <th class="num">リスク</th>
            <th class="num">リワード</th>
            <th class="num">リスクリワード</th>
          </tr>
        </thead>
        <tbody>
          {#each shown as r}
            <tr>
              <td class="num">{r.rank}</td>
              <td>{r.code}</td>
              <td><a href={tradingViewUrl(r.code)} target="_blank" rel="noopener noreferrer">{r.name}</a></td>
              <td class="num">{oku(r.market_cap_oku)}</td>
              <td>{r.method}</td>
              <td>{r.level}</td>
              <td class="num">{price(r.entry, 1)}</td>
              <td>{r.stop_line}</td>
              <td class="num">{price(r.stop, 1)}</td>
              <td class="num">{pct(r.hold_pct)} / {r.touches ?? '—'}</td>
              <td class="num">{pct(r.risk_pct, 2)}</td>
              <td class="num">{pct(r.reward_pct, 1)}</td>
              <td class="num">{dec(r.rr, 2)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    {#if !showAll && filtered.length > MOBILE_FIRST}
      <button type="button" style="margin-top: 10px" onclick={() => (showAll = true)}>
        すべて表示({filtered.length}件)
      </button>
    {/if}
    <p class="muted">並び順はリスクリワードの大きい順。同じ銘柄が複数の手法で候補になったときは、手法ごとに別の行で出す。</p>
  </section>
{/if}
