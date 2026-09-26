<script lang="ts">
  /** ヘッダー(基本設計書 §3・§4.3・§4.5)。基準日と最終更新を常に出す。 */
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { api, type SearchHit, type Status } from '../api';
  import { stamp, dateWithWeekday } from '../format';

  let { status = null as Status | null } = $props();

  let query = $state('');
  let hits = $state<SearchHit[]>([]);
  let open = $state(false);
  let timer: ReturnType<typeof setTimeout> | undefined;

  const market = $derived(page.url.pathname.startsWith('/market'));
  const weekly = $derived(page.url.pathname.startsWith('/weekly'));

  function search() {
    clearTimeout(timer);
    const q = query.trim();
    if (!q) {
      hits = [];
      open = false;
      return;
    }
    timer = setTimeout(async () => {
      try {
        hits = await api.search(q);
        open = hits.length > 0;
      } catch {
        hits = [];
        open = false;
      }
    }, 150);
  }

  async function pick(hit: SearchHit) {
    open = false;
    query = '';
    // 検索から判定表を開く(§8.6 の 4)
    await goto(`/weekly/verdicts?code=${hit.code}`);
  }
</script>

<header>
  <div class="row">
    <h1><a href="/market" style="color: inherit; text-decoration: none">株価ポータル</a></h1>
    <nav class="row" style="gap: 8px">
      <a href="/market" class:on={market}>市場概況</a>
      <a href="/weekly/verdicts" class:on={weekly}>週次の分析結果</a>
    </nav>
    <div class="grow"></div>
    <div class="finder">
      <input
        type="search"
        placeholder="コード・社名で検索"
        aria-label="銘柄の検索"
        bind:value={query}
        oninput={search}
        onfocus={() => (open = hits.length > 0)}
      />
      {#if open}
        <ul class="hits">
          {#each hits as hit}
            <li>
              <button type="button" onclick={() => pick(hit)}>
                <span class="code">{hit.code}</span>
                <span class="name">{hit.name}</span>
                {#if !hit.in_universe}<span class="muted">対象外</span>{/if}
              </button>
            </li>
          {/each}
        </ul>
      {/if}
    </div>
    <a href="/settings" aria-label="設定" title="設定">設定</a>
  </div>

  {#if status}
    <div class="row stamps">
      <span class="muted">
        データの週: {dateWithWeekday(status.market.data_week_end)} / 基準日: {dateWithWeekday(status.weekly.latest_date)}
      </span>
      <span class="muted">最終更新: {stamp(status.weekly.last_updated ?? status.market.last_updated)}</span>
      {#if status.market.delayed || status.weekly.delayed}
        <span class="notice notice--warn" style="padding: 2px 8px">
          更新が遅れています({status.delayed_after} を過ぎても前の週のままです)
        </span>
      {/if}
    </div>
  {/if}
</header>

<style>
  header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 8px 16px;
  }
  nav a {
    color: var(--text-sub);
    text-decoration: none;
    padding: 4px 8px;
  }
  nav a.on {
    color: var(--text);
    font-weight: 700;
    border-bottom: 2px solid var(--text);
  }
  .finder { position: relative; }
  .finder input { min-width: 200px; }
  .hits {
    position: absolute;
    right: 0;
    top: 46px;
    z-index: 20;
    margin: 0;
    padding: 4px;
    list-style: none;
    background: var(--surface);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius);
    min-width: 280px;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.08);
  }
  .hits button {
    width: 100%;
    text-align: left;
    border: 0;
    background: transparent;
    display: flex;
    gap: 8px;
    align-items: center;
    min-height: 44px;
  }
  .hits .code { font-variant-numeric: tabular-nums; color: var(--text-sub); }
  .stamps { margin-top: 4px; gap: 12px; }
  @media (max-width: 767px) {
    .finder input { min-width: 120px; }
    h1 { font-size: 16px; }
  }
</style>
