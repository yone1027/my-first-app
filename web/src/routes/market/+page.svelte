<script lang="ts">
  /** G-11 市場概況 ① 日本市場(基本設計書 §5.1)。 */
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import Cautions from '$lib/components/Cautions.svelte';
  import CardState from '$lib/components/CardState.svelte';
  import Chart from '$lib/components/Chart.svelte';
  import HierarchyNav from '$lib/components/HierarchyNav.svelte';
  import PeriodPicker from '$lib/components/PeriodPicker.svelte';
  import { api, ApiFailure, type Japan } from '$lib/api';
  import { cho, dec, pct, pt, rank, times, weekRange } from '$lib/format';
  import { INDICATOR_LABEL, INVESTOR_LABEL, INVESTOR_ORDER, SEGMENT_LABEL } from '$lib/labels';
  import { cssValue } from '$lib/theme';

  const period = $derived(page.url.searchParams.get('period') ?? '13w');
  let data = $state<Japan | null>(null);
  let failure = $state<string | null>(null);

  $effect(() => {
    const want = period;
    api
      .japan(want)
      .then((body) => {
        data = body;
        failure = null;
        // 不正な値は API が既定に直すので、URL も直す(§5.2)
        if (body.params.period !== want) goto(`/market?period=${body.params.period}`, { replaceState: true });
      })
      .catch((e: ApiFailure) => {
        data = null;
        failure = e.body?.error === 'not_built' ? '市場概況の集計がまだ作られていません' : `読み込みに失敗しました(${e.status})`;
      });
  });

  const labels = $derived((data?.weeks ?? []).map((w) => weekRange(w.start, w.end)));
  const shortMarks = $derived(
    (data?.weeks ?? []).map((w, i) => (w.short ? { xAxis: i } : null)).filter(Boolean) as { xAxis: number }[]
  );

  /** TOPIX と売買代金。上下2つの grid で横軸を共有する(§8.4)。 */
  const topixOption = $derived.by(() => {
    if (!data) return {};
    const text = cssValue('--text-sub', '#57534A');
    return {
      animation: false,
      textStyle: { fontFamily: cssValue('--font-family', 'sans-serif'), color: text },
      grid: [
        { left: 60, right: 20, top: 24, height: 130 },
        { left: 60, right: 20, top: 186, height: 70 }
      ],
      xAxis: [
        { type: 'category' as const, data: labels, gridIndex: 0, axisLabel: { show: false }, axisLine: { lineStyle: { color: cssValue('--border-strong') } } },
        { type: 'category' as const, data: labels, gridIndex: 1, axisLabel: { color: text, fontSize: 10, interval: Math.ceil(labels.length / 7) }, axisLine: { lineStyle: { color: cssValue('--border-strong') } } }
      ],
      yAxis: [
        { type: 'value' as const, gridIndex: 0, scale: true, splitLine: { lineStyle: { color: cssValue('--border') } }, axisLabel: { color: text, fontSize: 10 } },
        { type: 'value' as const, gridIndex: 1, splitLine: { show: false }, axisLabel: { color: text, fontSize: 10, formatter: (v: number) => `${(v / 1e12).toFixed(0)}兆` } }
      ],
      legend: { top: 0, textStyle: { color: text, fontSize: 11 }, data: ['TOPIX', '13週線', '26週線', '52週線'] },
      tooltip: { trigger: 'axis', axisPointer: { type: 'cross' as const } },
      series: [
        { name: 'TOPIX', type: 'line' as const, data: data.topix.close, showSymbol: false, lineStyle: { width: 2, color: cssValue('--text') }, itemStyle: { color: cssValue('--text') } },
        { name: '13週線', type: 'line' as const, data: data.topix.ma13, showSymbol: false, lineStyle: { width: 1, color: cssValue('--up') }, itemStyle: { color: cssValue('--up') } },
        { name: '26週線', type: 'line' as const, data: data.topix.ma26, showSymbol: false, lineStyle: { width: 1, color: cssValue('--down') }, itemStyle: { color: cssValue('--down') } },
        { name: '52週線', type: 'line' as const, data: data.topix.ma52, showSymbol: false, lineStyle: { width: 1, color: cssValue('--growth') }, itemStyle: { color: cssValue('--growth') } },
        {
          name: '売買代金',
          type: 'bar' as const,
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: data.turnover.series,
          itemStyle: { color: cssValue('--border-strong') },
          // 営業日5日未満の週に ▲ を描く(§8.4)
          markPoint: {
            symbol: 'triangle' as const,
            symbolSize: 7,
            itemStyle: { color: cssValue('--text-muted') },
            label: { show: false },
            data: shortMarks.map((m) => ({ coord: [m.xAxis, 0], yAxis: 0 }))
          }
        },
        { name: '13週平均', type: 'line' as const, xAxisIndex: 1, yAxisIndex: 1, data: data.turnover.ma13, showSymbol: false, lineStyle: { width: 1.5, color: cssValue('--down') } }
      ]
    };
  });
</script>

<HierarchyNav at={1} {period} />
<div class="row" style="margin: 10px 0">
  <h1>お金の流れ: 日本市場</h1>
  <div class="grow"></div>
  <PeriodPicker {period} onpick={(next: string) => goto(`/market?period=${next}`)} />
</div>

<CardState error={failure} />

{#if data}
  <Cautions extra={['売買代金の集計は ETF・REIT と TOKYO PRO MARKET を除く。東証が公表する売買代金とは一致しない']} />

  <!-- (1) 量: 売買代金 -->
  <section class="card">
    <h2>1. 量 — 今どれだけお金が入っているか</h2>
    <div class="row" style="gap: 28px">
      <div><div class="muted">直近の週({weekRange(data.as_of_week.start, data.as_of_week.end)})</div><strong style="font-size: 22px">{cho(data.turnover.latest)}</strong></div>
      <div><div class="muted">13週平均</div>{cho(data.turnover.avg13)}</div>
      <div><div class="muted">13週平均との比</div>{dec(data.turnover.ratio13, 2)}倍</div>
      <div><div class="muted">期間の中での位置</div>{rank(data.turnover.percentile)} / 100</div>
    </div>
    <Chart option={topixOption} height={280} />
    <p class="muted">▲ は営業日が5日に足りない週。移動平均線は凡例を押すと表示を切り替えられる。</p>
  </section>

  <!-- (2) 配分: 市場区分 -->
  <section class="card">
    <h2>2. 配分 — どこにお金があるか</h2>
    <div class="bar">
      {#each data.allocation as a}
        {#if a.share_latest}
          <div class="seg" style="width: {a.share_latest}%; background: var(--{a.segment})" title="{SEGMENT_LABEL[a.segment]} {pct(a.share_latest)}"></div>
        {/if}
      {/each}
    </div>
    <div class="row" style="gap: 20px; margin-top: 8px">
      {#each data.allocation as a}
        <div class="row" style="gap: 6px">
          <span class="swatch" style="background: var(--{a.segment})"></span>
          <span>{SEGMENT_LABEL[a.segment]}</span>
          <strong>{pct(a.share_latest)}</strong>
          <span class="muted">期間で {pt(a.share_change_pt)}</span>
        </div>
      {/each}
    </div>
    <p style="margin-top: 10px"><a href={`/market/segments?period=${period}`}>市場区分ごとに見る ›</a></p>
  </section>

  <!-- (3) 主体別売買動向 -->
  <section class="card">
    <h2>主体別売買動向(東証全体)</h2>
    {#if data.investors.subjects.length === 0}
      <CardState error={data.investors.not_built ? '集計がまだ作られていません(投資部門別情報の取得が未実装)' : null} empty={!data.investors.not_built} />
      <p class="muted">この欄は、J-Quants の投資部門別情報を取得する処理を作ってから表示します。</p>
    {:else}
      <div class="row" style="gap: 16px">
        {#each INVESTOR_ORDER as key, i}
          <span class="row" style="gap: 6px"><span class="swatch" style="background: var(--investor-{i})"></span>{INVESTOR_LABEL[key]}</span>
        {/each}
      </div>
    {/if}
  </section>

  <!-- (4) 業績と評価 -->
  <section class="card">
    <h2>市場全体の EPS・PER</h2>
    {#if data.valuation.per.at(-1) == null}
      <CardState empty emptyText="この期間の EPS・PER はありません" />
    {:else}
      <div class="row" style="gap: 28px">
        <div><div class="muted">PER(会社予想)</div><strong style="font-size: 20px">{times(data.valuation.per.at(-1), 1)}</strong></div>
        <div><div class="muted">EPS</div>{dec(data.valuation.eps.at(-1), 1)}</div>
        <div><div class="muted">対象銘柄</div>{data.valuation.n_target ?? '—'}</div>
        <div><div class="muted">赤字予想で除いた銘柄</div>{data.valuation.n_excluded_loss ?? '—'}</div>
      </div>
      <p class="sub" style="margin-top: 10px">
        期間の値動きの分解: TOPIX {pct(data.valuation.topix_change_pct, 1, true)}
        ={' '}EPS {pct(data.valuation.eps_change_pct, 1, true)} × PER {pct(data.valuation.per_change_pct, 1, true)}
      </p>
      <p class="muted">3つは掛け算の関係なので、足し算では一致しない。PER は会社予想で、赤字予想の会社を除く。</p>
    {/if}
  </section>

  <!-- (5) 日本をとりまく指標 -->
  <section class="card">
    <h2>日本をとりまく指標</h2>
    <div class="row" style="gap: 24px">
      {#each data.indicators as ind}
        <div>
          <div class="muted">{INDICATOR_LABEL[ind.key]?.name ?? ind.key}</div>
          {#if ind.latest == null}
            <span class="muted">—</span>
          {:else}
            <strong>{dec(ind.latest, 2)}{INDICATOR_LABEL[ind.key]?.unit ?? ''}</strong>
          {/if}
        </div>
      {/each}
    </div>
    {#if data.indicators.every((i) => i.latest == null)}
      <p class="muted" style="margin-top: 8px">この欄は、財務省・日本銀行・EIA からデータを取得する処理を作ってから表示します。</p>
    {/if}
  </section>
{/if}

<style>
  .bar { display: flex; height: 26px; border-radius: 4px; overflow: hidden; background: var(--surface-alt); }
  .seg { height: 100%; }
  .swatch { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
</style>
