<script lang="ts">
  /** 主体別売買動向(基本設計書 §5.1 (5)・§5.2 (3)、詳細設計書 §8.4)。
   *  積み上げ棒(買い越しは0より上、売り越しは0より下)に TOPIX の線を重ねる。 */
  import Chart from './Chart.svelte';
  import CardState from './CardState.svelte';
  import type { Investors, Series, Week } from '../api';
  import { cho, dec, weekRange } from '../format';
  import { INVESTOR_LABEL, INVESTOR_ORDER } from '../labels';
  import { cssValue } from '../theme';

  let {
    investors = null as Investors | null,
    weeks = [] as Week[],
    topix = null as Series | null,
    recent = 2,
    title = '主体別売買動向'
  } = $props();

  /** 補足(基本設計書 §5.1 (5))。 */
  const NOTES: Record<string, string> = {
    business_cos: '自社株買いを含む',
    trust_banks: '年金の売買を多く含む'
  };

  // 既定は6つとも表示
  let shown = $state(new Set(INVESTOR_ORDER));

  function toggle(key: string) {
    const next = new Set(shown);
    next.has(key) ? next.delete(key) : next.add(key);
    shown = next;
  }

  const byKey = $derived(new Map((investors?.subjects ?? []).map((s) => [s.key, s])));
  const labels = $derived(weeks.map((w) => weekRange(w.start, w.end)));
  const colourOf = (key: string) => cssValue(`--investor-${INVESTOR_ORDER.indexOf(key)}`);

  /** 未公表の週(右端)。公表が1週以上遅れるので必ず出る(§6.7)。 */
  const unpublishedFrom = $derived.by(() => {
    const series = byKey.get('foreigners')?.series ?? [];
    for (let i = series.length - 1; i >= 0; i -= 1) {
      if (series[i] != null) return i + 1;
    }
    return series.length;
  });

  const option = $derived.by(() => {
    if (!investors || investors.subjects.length === 0) return {};
    const text = cssValue('--text-sub');
    const bars = INVESTOR_ORDER.filter((k) => shown.has(k)).flatMap((key) => {
      const series = byKey.get(key)?.series ?? [];
      const colour = colourOf(key);
      // 正と負で stack を分ける(§8.4)
      return [
        {
          name: INVESTOR_LABEL[key],
          type: 'bar' as const,
          stack: 'pos',
          yAxisIndex: 1,
          itemStyle: { color: colour },
          data: series.map((v) => (v != null && v > 0 ? v : null))
        },
        {
          name: INVESTOR_LABEL[key],
          type: 'bar' as const,
          stack: 'neg',
          yAxisIndex: 1,
          itemStyle: { color: colour },
          data: series.map((v) => (v != null && v < 0 ? v : null)),
          tooltip: { show: false }
        }
      ];
    });

    // 右の軸は、選んだ主体の正の合計の最大と負の合計の最小から決める(§8.4)
    let top = 0;
    let bottom = 0;
    for (let i = 0; i < labels.length; i += 1) {
      let plus = 0;
      let minus = 0;
      for (const key of shown) {
        const v = byKey.get(key)?.series?.[i];
        if (v == null) continue;
        v > 0 ? (plus += v) : (minus += v);
      }
      top = Math.max(top, plus);
      bottom = Math.min(bottom, minus);
    }
    const pad = Math.max(top, -bottom) * 0.1 || 1;

    return {
      animation: false,
      textStyle: { fontFamily: cssValue('--font-family', 'sans-serif'), color: text },
      grid: { left: 58, right: 62, top: 16, bottom: 40 },
      xAxis: {
        type: 'category' as const,
        data: labels,
        axisLabel: { color: text, fontSize: 10, interval: Math.ceil(labels.length / 7) }
      },
      yAxis: [
        {
          type: 'value' as const,
          name: 'TOPIX',
          nameTextStyle: { fontSize: 10, color: text },
          scale: true,
          splitLine: { lineStyle: { color: cssValue('--border') } },
          axisLabel: { color: text, fontSize: 10 }
        },
        {
          type: 'value' as const,
          name: '買い越し(兆円)',
          nameTextStyle: { fontSize: 10, color: text },
          min: bottom - pad,
          max: top + pad,
          splitLine: { show: false },
          axisLabel: { color: text, fontSize: 10, formatter: (v: number) => (v / 1e12).toFixed(1) }
        }
      ],
      tooltip: { trigger: 'axis' as const, axisPointer: { type: 'shadow' as const } },
      series: [
        ...bars,
        ...(topix
          ? [
              {
                name: 'TOPIX',
                type: 'line' as const,
                yAxisIndex: 0,
                data: topix,
                showSymbol: false,
                lineStyle: { width: 2, color: cssValue('--text') },
                itemStyle: { color: cssValue('--text') },
                z: 10,
                // 未公表の週を網かけにする(§8.4)
                markArea:
                  unpublishedFrom < labels.length
                    ? {
                        itemStyle: { color: cssValue('--surface-alt') },
                        label: { show: true, formatter: '未公表', fontSize: 10, color: text, position: 'insideTop' as const },
                        data: [[{ xAxis: unpublishedFrom }, { xAxis: labels.length - 1 }]]
                      }
                    : undefined
              }
            ]
          : [])
      ]
    };
  });
</script>

<section class="card">
  <div class="row">
    <h2 style="margin: 0">{title}{#if investors}<span class="muted">({investors.section === 'all' ? '東証全体' : investors.section})</span>{/if}</h2>
    <div class="grow"></div>
    {#if investors && investors.subjects.length > 0}
      <span class="muted">{shown.size} / 6 を表示</span>
      <button type="button" onclick={() => (shown = new Set(INVESTOR_ORDER))}>すべて選ぶ</button>
      <button type="button" onclick={() => (shown = new Set())}>すべて外す</button>
    {/if}
  </div>

  {#if !investors || investors.subjects.length === 0}
    <CardState error={investors?.not_built ? '集計がまだ作られていません' : null} empty={!investors?.not_built} />
    {#if investors?.not_built}
      <p class="muted">{investors.not_built}</p>
    {/if}
  {:else}
    {#if investors.summary}
      <p>
        直近{recent}週で、買い越しが期間平均より
        <strong style="color: var(--up)">増えている主体:</strong>
        {investors.summary.up.map((k) => INVESTOR_LABEL[k]).join('、') || '—'}
        　<strong style="color: var(--down)">減っている主体:</strong>
        {investors.summary.down.map((k) => INVESTOR_LABEL[k]).join('、') || '—'}
      </p>
    {/if}
    {#if investors.latest_published}
      <p class="muted">
        最新は {weekRange(null, investors.latest_published.end)?.replace('—', '')}
        {investors.latest_published.end} までの週の分({investors.latest_published.pub_date} 公表)。
        対象の週の翌週に公表されるため、株価より1週以上遅れる。
      </p>
    {/if}

    <Chart {option} height={280} />

    <div class="scroll-x">
      <table>
        <thead>
          <tr>
            <th>主体(押すと表示を切り替え)</th>
            <th class="num">期間の買い越し額</th>
            <th class="num">1週あたり: 直近{recent}週</th>
            <th class="num">1週あたり: 期間</th>
          </tr>
        </thead>
        <tbody>
          {#each INVESTOR_ORDER as key}
            {@const s = byKey.get(key)}
            <tr class:off={!shown.has(key)}>
              <td>
                <button type="button" class="pick" onclick={() => toggle(key)} aria-pressed={shown.has(key)}>
                  <span class="swatch" class:hollow={!shown.has(key)} style="background: var(--investor-{INVESTOR_ORDER.indexOf(key)}); border-color: var(--investor-{INVESTOR_ORDER.indexOf(key)})"></span>
                  {INVESTOR_LABEL[key]}
                  {#if NOTES[key]}<span class="muted">({NOTES[key]})</span>{/if}
                </button>
              </td>
              <td class="num">{cho(s?.total ?? null, 2)}</td>
              <td class="num">{cho(s?.avg_recent ?? null, 2)}</td>
              <td class="num">{cho(s?.avg_period ?? null, 2)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    {#if shown.size === 0}
      <p class="muted">主体をすべて外しています。TOPIX の線だけを描いています。</p>
    {/if}
  {/if}
</section>

<style>
  .swatch { width: 12px; height: 12px; border-radius: 3px; display: inline-block; border: 2px solid transparent; }
  .swatch.hollow { background: transparent !important; }
  /* 共通 CSS の button[aria-pressed='true'] は文字色を白にする(選択中のボタンの見せ方)。
     この行は「押せる一覧」なので、その見せ方は使わない(2026-09-27 に白文字で消えた)。 */
  .pick,
  .pick[aria-pressed='true'] {
    border: 0;
    background: transparent;
    color: var(--text);
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 44px;
    text-align: left;
    padding: 0;
  }
  tr.off { opacity: 0.5; }
</style>
