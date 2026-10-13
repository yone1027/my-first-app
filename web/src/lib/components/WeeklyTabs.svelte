<script lang="ts">
  /** 週次の画面で共通の見出し(基本設計書 §5.4 (1))。基準日の選択とタブ。 */
  import { goto } from '$app/navigation';
  import { dateWithWeekday } from '../format';
  import type { Dates } from '../api';

  let {
    dates = null as Dates | null,
    date = '',
    tab = 'verdicts',
    counts = {} as Record<string, number | null>
  } = $props();

  const list = $derived(dates?.dates ?? []);
  const index = $derived(list.findIndex((d) => d.date === date));
  const newest = $derived(index === 0);
  const oldest = $derived(index >= 0 && index === list.length - 1);
  const has = $derived(list[index]?.has ?? { verdicts: true, picks: true, candidates: true });

  // 推奨銘柄は「来週の推奨銘柄」と「推奨銘柄の成績」の2つをまとめたタブ(2026-10-13 決定)
  const TABS = [
    { key: 'verdicts', label: '手法ごとの判定表', href: '/weekly/verdicts' },
    { key: 'recommend', label: '推奨銘柄', href: '/weekly/picks' },
    { key: 'candidates', label: 'テクニカルスクリーニング', href: '/weekly/candidates' }
  ];
  const SUB_TABS = [
    { key: 'picks', label: '来週の推奨銘柄', href: '/weekly/picks' },
    // 成績は全期間の一覧なので基準日を持たない(G-24)
    { key: 'evaluation', label: '推奨銘柄の成績', href: '/weekly/evaluation' }
  ];
  const ROUTES = [...TABS, ...SUB_TABS];
  const isRecommend = $derived(tab === 'picks' || tab === 'evaluation');
  const datedTab = $derived(tab !== 'evaluation');

  function tabHref(t: { key: string; href: string }): string {
    return t.key === 'evaluation' || !date ? t.href : `${t.href}?date=${date}`;
  }

  function isOn(key: string): boolean {
    return key === 'recommend' ? isRecommend : tab === key;
  }

  function isEmpty(key: string): boolean {
    if (!datedTab) return false;
    const k = key === 'recommend' ? 'picks' : key;
    return k in has && !has[k as keyof typeof has];
  }

  function move(step: number) {
    const next = list[index + step];
    if (next) goto(`${ROUTES.find((t) => t.key === tab)!.href}?date=${next.date}`);
  }
</script>

<div class="row" style="margin: 10px 0">
  <h1>週次の分析結果</h1>
  <div class="grow"></div>
  {#if datedTab}
  <div class="row" style="gap: 4px">
    <button type="button" onclick={() => move(1)} disabled={oldest || index < 0} aria-label="前の基準日">◀</button>
    <select
      aria-label="基準日の選択"
      value={date}
      onchange={(e) => goto(`${ROUTES.find((t) => t.key === tab)!.href}?date=${(e.currentTarget as HTMLSelectElement).value}`)}
    >
      {#each list as d, i}
        <option value={d.date}>{dateWithWeekday(d.date)}{i === 0 ? '(最新)' : ''}</option>
      {/each}
    </select>
    <button type="button" onclick={() => move(-1)} disabled={newest || index < 0} aria-label="次の基準日">▶</button>
  </div>
  {/if}
</div>

<nav class="tabs" aria-label="週次のタブ">
  {#each TABS as t}
    <a href={tabHref(t)} class:on={isOn(t.key)} class:empty={isEmpty(t.key)}>
      {t.label}{#if counts[t.key] != null}({counts[t.key]}){/if}
    </a>
  {/each}
</nav>

{#if isRecommend}
  <nav class="tabs sub" aria-label="推奨銘柄のタブ">
    {#each SUB_TABS as t}
      <a href={tabHref(t)} class:on={tab === t.key} class:empty={isEmpty(t.key)}>
        {t.label}{#if counts[t.key] != null}({counts[t.key]}){/if}
      </a>
    {/each}
  </nav>
{/if}

<style>
  .tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border); margin-bottom: var(--gap); flex-wrap: wrap; }
  .tabs a {
    padding: 10px 12px;
    text-decoration: none;
    color: var(--text-sub);
    border-bottom: 2px solid transparent;
    min-height: 44px;
    display: flex;
    align-items: center;
  }
  .tabs a.on { color: var(--text); font-weight: 700; border-bottom-color: var(--text); }
  .tabs a.empty { color: var(--text-muted); }
  .tabs.sub { border-bottom: none; margin-top: calc(-1 * var(--gap) + 4px); }
  .tabs.sub a { min-height: 40px; padding: 8px 12px; font-size: 0.95em; }
</style>
