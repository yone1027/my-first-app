<script lang="ts">
  /** G-13 市場概況 ③ 業種(基本設計書 §5.3)。 */
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import Cautions from '$lib/components/Cautions.svelte';
  import CardState from '$lib/components/CardState.svelte';
  import HierarchyNav from '$lib/components/HierarchyNav.svelte';
  import PeriodPicker from '$lib/components/PeriodPicker.svelte';
  import { api, ApiFailure, type Sectors } from '$lib/api';
  import { pct, weekRange } from '$lib/format';
  import { SEGMENT_LABEL } from '$lib/labels';

  const period = $derived(page.url.searchParams.get('period') ?? '13w');
  const scope = $derived(page.url.searchParams.get('scope') ?? 'all');
  let data = $state<Sectors | null>(null);
  let failure = $state<string | null>(null);

  $effect(() => {
    const [p, s] = [period, scope];
    api
      .sectors(p, s)
      .then((body) => {
        data = body;
        failure = null;
        if (body.params.period !== p || body.params.scope !== s) {
          goto(`/market/sectors?period=${body.params.period}&scope=${body.params.scope}`, { replaceState: true });
        }
      })
      .catch((e: ApiFailure) => {
        data = null;
        failure = e.body?.error === 'not_built' ? '市場概況の集計がまだ作られていません' : `読み込みに失敗しました(${e.status})`;
      });
  });

  /** ヒートマップの色。±30% 以上は同じ色で飽和(基本設計書 §5.3)。 */
  function heatColour(value: number | null): string {
    if (value == null) return 'var(--surface-alt)';
    const t = Math.max(-1, Math.min(1, value / 30));
    const to = t >= 0 ? 'var(--up)' : 'var(--down)';
    return `color-mix(in srgb, ${to} ${Math.round(Math.abs(t) * 100)}%, var(--surface))`;
  }

  const weekLabels = $derived((data?.weeks ?? []).map((w) => weekRange(w.start, w.end)));
  /** 0% をまたぐ所に区切り線を引く(基本設計書 §5.3)。 */
  const crossAt = $derived(
    (data?.sectors ?? []).findIndex((s) => (s.period_average_ratio ?? 0) < 0)
  );
</script>

<HierarchyNav at={3} {period} {scope} />
<div class="row" style="margin: 10px 0">
  <h1>お金の流れ: 業種(33業種)</h1>
  <div class="grow"></div>
  <PeriodPicker {period} onpick={(next: string) => goto(`/market/sectors?period=${next}&scope=${scope}`)} />
</div>

<div class="row" style="margin-bottom: 10px; gap: 6px">
  <span class="muted">対象</span>
  {#each ['all', 'prime', 'standard', 'growth'] as key}
    <button type="button" aria-pressed={scope === key} onclick={() => goto(`/market/sectors?period=${period}&scope=${key}`)}>
      {SEGMENT_LABEL[key]}
    </button>
  {/each}
</div>

<CardState error={failure} />

{#if data}
  <Cautions />

  <section class="card">
    <h2>要約</h2>
    <p>
      <strong style="color: var(--up)">集まっている:</strong>
      {#each data.summary.up as s, i}{i > 0 ? '、' : ''}{s.name} {pct(s.ratio, 1, true)}{/each}
    </p>
    <p>
      <strong style="color: var(--down)">抜けている:</strong>
      {#each data.summary.down as s, i}{i > 0 ? '、' : ''}{s.name} {pct(s.ratio, 1, true)}{/each}
    </p>
    <p class="muted">
      期間平均比 = 直近{data.params.recent}週の平均シェア ÷ 期間({data.params.weeks}週)の平均シェア − 1。
      上位3と下位3の業種は太字。
    </p>
  </section>

  <section class="card">
    <h2>業種の一覧とヒートマップ</h2>
    <div class="scroll-x">
      <table>
        <thead>
          <tr>
            <th>業種</th>
            <th>期間の週ごと(左が古い)</th>
            <th class="num">直近週のシェア</th>
            <th class="num">直近の期間平均比</th>
          </tr>
        </thead>
        <tbody>
          {#each data.sectors as s, i}
            <tr class:divider={i === crossAt && crossAt > 0}>
              <td style="font-weight: {s.emphasis ? 700 : 400}">{s.name}</td>
              <td>
                <div class="heat">
                  {#each s.heat as cell, j}
                    <span
                      class="cell"
                      style="background: {heatColour(cell)}"
                      title="{weekLabels[j]}: {pct(cell, 1, true)}"
                    ></span>
                  {/each}
                </div>
              </td>
              <td class="num">{pct(s.share_latest, 2)}</td>
              <td class="num">
                <div class="row" style="gap: 6px; justify-content: flex-end">
                  <span class="meter">
                    {#if s.period_average_ratio != null}
                      <span
                        class="fill"
                        style="
                          width: {Math.min(Math.abs(s.period_average_ratio), 60) / 60 * 50}%;
                          {s.period_average_ratio >= 0 ? 'left: 50%' : 'right: 50%'};
                          background: {s.period_average_ratio >= 0 ? 'var(--up)' : 'var(--down)'}"
                      ></span>
                    {/if}
                  </span>
                  <span style="min-width: 58px; display: inline-block">{pct(s.period_average_ratio, 1, true)}</span>
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    <div class="row" style="margin-top: 10px; gap: 8px">
      <span class="muted">期間平均より少ない</span>
      <span class="legend">
        {#each [-30, -20, -10, 0, 10, 20, 30] as v}
          <span class="cell" style="background: {heatColour(v)}"></span>
        {/each}
      </span>
      <span class="muted">多い(±30%以上は同じ色)</span>
    </div>
    <p class="muted">業種を押したときの動き(④銘柄の段)は未決。初版では何も起きない。</p>
  </section>
{/if}

<style>
  .heat { display: flex; gap: 1px; }
  .cell { width: 12px; height: 18px; display: inline-block; border-radius: 1px; }
  .legend { display: flex; gap: 1px; }
  .meter { position: relative; display: inline-block; width: 80px; height: 10px; background: var(--surface-alt); border-radius: 2px; }
  .meter .fill { position: absolute; top: 0; height: 100%; border-radius: 2px; }
  tr.divider td { border-top: 2px dotted var(--border-strong); }
</style>
