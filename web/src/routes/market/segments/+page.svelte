<script lang="ts">
  /** G-12 市場概況 ② 市場区分(基本設計書 §5.2)。
   *  3区分分を最初に受け取り、切り替えでは API を呼び直さない(§8.3)。 */
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import Cautions from '$lib/components/Cautions.svelte';
  import CardState from '$lib/components/CardState.svelte';
  import Chart from '$lib/components/Chart.svelte';
  import HierarchyNav from '$lib/components/HierarchyNav.svelte';
  import Investors from '$lib/components/Investors.svelte';
  import PeriodPicker from '$lib/components/PeriodPicker.svelte';
  import { api, ApiFailure, type Segments } from '$lib/api';
  import { cho, dec, pct, times, weekRange } from '$lib/format';
  import { SEGMENT_LABEL } from '$lib/labels';
  import { cssValue } from '$lib/theme';

  const period = $derived(page.url.searchParams.get('period') ?? '13w');
  let data = $state<Segments | null>(null);
  let failure = $state<string | null>(null);
  let picked = $state('prime');

  $effect(() => {
    const want = period;
    api
      .segments(want)
      .then((body) => {
        data = body;
        failure = null;
      })
      .catch((e: ApiFailure) => {
        data = null;
        failure = e.body?.error === 'not_built' ? '市場概況の集計がまだ作られていません' : `読み込みに失敗しました(${e.status})`;
      });
  });

  const labels = $derived((data?.weeks ?? []).map((w) => weekRange(w.start, w.end)));
  const current = $derived(data?.segments.find((s) => s.segment === picked) ?? null);

  /** シェアの推移。期間平均は markLine、直近の範囲は markArea(§8.4)。 */
  const shareOption = $derived.by(() => {
    if (!data || !current) return {};
    const text = cssValue('--text-sub');
    const from = labels.length - data.params.recent;
    return {
      animation: false,
      textStyle: { fontFamily: cssValue('--font-family', 'sans-serif'), color: text },
      grid: { left: 52, right: 52, top: 20, bottom: 40 },
      xAxis: { type: 'category' as const, data: labels, axisLabel: { color: text, fontSize: 10, interval: Math.ceil(labels.length / 7) } },
      yAxis: [
        { type: 'value' as const, name: 'シェア(%)', nameTextStyle: { fontSize: 10, color: text }, scale: true, splitLine: { lineStyle: { color: cssValue('--border') } }, axisLabel: { color: text, fontSize: 10 } },
        { type: 'value' as const, name: '売買代金', nameTextStyle: { fontSize: 10, color: text }, splitLine: { show: false }, axisLabel: { color: text, fontSize: 10, formatter: (v: number) => `${(v / 1e12).toFixed(0)}兆` } }
      ],
      tooltip: { trigger: 'axis' as const },
      series: [
        {
          name: '売買代金',
          type: 'bar' as const,
          yAxisIndex: 1,
          data: current.turnover,
          itemStyle: { color: cssValue('--border') }
        },
        {
          name: 'シェア',
          type: 'line' as const,
          data: current.share,
          showSymbol: false,
          lineStyle: { width: 2, color: `var(--${picked})` === '' ? cssValue('--text') : cssValue(`--${picked}`) },
          itemStyle: { color: cssValue(`--${picked}`) },
          markLine: {
            silent: true,
            symbol: 'none' as const,
            label: { formatter: '期間平均', fontSize: 10, color: text },
            lineStyle: { type: 'dashed' as const, color: cssValue('--text-muted') },
            data: [{ yAxis: current.share_avg_period ?? 0 }]
          },
          markArea: {
            itemStyle: { color: cssValue('--surface-alt') },
            data: [[{ xAxis: Math.max(from, 0) }, { xAxis: labels.length - 1 }]]
          }
        }
      ]
    };
  });
</script>

<HierarchyNav at={2} {period} />
<div class="row" style="margin: 10px 0">
  <h1>お金の流れ: 市場区分</h1>
  <div class="grow"></div>
  <PeriodPicker {period} onpick={(next: string) => goto(`/market/segments?period=${next}`)} />
</div>

<CardState error={failure} />

{#if data}
  <Cautions />

  <section class="card">
    <h2>区分ごとのシェアと評価</h2>
    <div class="scroll-x">
      <table>
        <thead>
          <tr>
            <th>市場区分</th>
            <th class="num">直近のシェア</th>
            <th class="num">期間の平均</th>
            <th class="num">期間平均比</th>
            <th class="num">直近の売買代金</th>
            <th class="num">PER</th>
            <th class="num">利益の合計の変化</th>
            <th class="num">対象銘柄</th>
          </tr>
        </thead>
        <tbody>
          {#each data.segments as s}
            <tr>
              <td><span class="swatch" style="background: var(--{s.segment})"></span> {SEGMENT_LABEL[s.segment]}</td>
              <td class="num">{pct(s.share_latest, 2)}</td>
              <td class="num">{pct(s.share_avg_period, 2)}</td>
              <td class="num" style="color: {(s.period_average_ratio ?? 0) >= 0 ? 'var(--up)' : 'var(--down)'}">
                {pct(s.period_average_ratio, 1, true)}
              </td>
              <td class="num">{cho(s.turnover.at(-1))}</td>
              <td class="num">{times(s.per.at(-1), 1)}</td>
              <td class="num">{pct(s.np_change_pct, 1, true)}</td>
              <td class="num">{s.n_target ?? '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    <p class="muted">②の区分では EPS を出さない。EPS は東証全体の指数(TOPIX)にひもづく値のため、PER と利益の合計の変化を出す。</p>
  </section>

  <section class="card">
    <div class="row">
      <h2 style="margin: 0">シェアの推移</h2>
      <div class="grow"></div>
      {#each data.segments as s}
        <button type="button" aria-pressed={picked === s.segment} onclick={() => (picked = s.segment)}>
          {SEGMENT_LABEL[s.segment]}
        </button>
      {/each}
    </div>
    {#if current}
      <Chart option={shareOption} height={260} />
      <p class="muted">
        点線は期間の平均シェア、網かけは直近{data.params.recent}週。
        直近の平均 {pct(current.share_avg_recent, 2)} ÷ 期間の平均 {pct(current.share_avg_period, 2)} − 1 =
        <strong>{pct(current.period_average_ratio, 1, true)}</strong>
      </p>
      <p><a href={`/market/sectors?period=${period}&scope=${picked}`}>{SEGMENT_LABEL[picked]}の業種を見る ›</a></p>
    {/if}
  </section>

  {#if current}
    <Investors
      investors={current.investors}
      weeks={data.weeks}
      recent={data.params.recent}
      title={`主体別売買動向 — ${SEGMENT_LABEL[picked]}`}
    />
  {/if}
{/if}

<style>
  .swatch { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
</style>
