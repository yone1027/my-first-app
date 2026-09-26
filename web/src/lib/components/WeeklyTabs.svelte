<script lang="ts">
  /** 週次の3画面で共通の見出し(基本設計書 §5.4 (1))。基準日の選択とタブ。 */
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

  const TABS = [
    { key: 'verdicts', label: '手法ごとの判定表', href: '/weekly/verdicts' },
    { key: 'picks', label: '来週の買い注文の候補', href: '/weekly/picks' },
    { key: 'candidates', label: '買い候補(パターン)', href: '/weekly/candidates' }
  ];

  function move(step: number) {
    const next = list[index + step];
    if (next) goto(`${TABS.find((t) => t.key === tab)!.href}?date=${next.date}`);
  }
</script>

<div class="row" style="margin: 10px 0">
  <h1>週次の分析結果</h1>
  <div class="grow"></div>
  <div class="row" style="gap: 4px">
    <button type="button" onclick={() => move(1)} disabled={oldest || index < 0} aria-label="前の基準日">◀</button>
    <select
      aria-label="基準日の選択"
      value={date}
      onchange={(e) => goto(`${TABS.find((t) => t.key === tab)!.href}?date=${(e.currentTarget as HTMLSelectElement).value}`)}
    >
      {#each list as d, i}
        <option value={d.date}>{dateWithWeekday(d.date)}{i === 0 ? '(最新)' : ''}</option>
      {/each}
    </select>
    <button type="button" onclick={() => move(-1)} disabled={newest || index < 0} aria-label="次の基準日">▶</button>
  </div>
</div>

<nav class="tabs" aria-label="週次のタブ">
  {#each TABS as t}
    <a
      href={`${t.href}?date=${date}`}
      class:on={tab === t.key}
      class:empty={!has[t.key as keyof typeof has]}
    >
      {t.label}{#if counts[t.key] != null}({counts[t.key]}){/if}
    </a>
  {/each}
</nav>

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
</style>
