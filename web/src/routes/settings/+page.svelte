<script lang="ts">
  /** G-30 設定(基本設計書 §5.7)。この端末だけの色の上書き。 */
  import { onMount } from 'svelte';
  import { contrast, CSS_VARS, defaultsOf, init, loadOverrides, merged, saveOverrides, type Theme } from '$lib/theme';
  import { dec } from '$lib/format';
  import { INVESTOR_LABEL, INVESTOR_ORDER } from '$lib/labels';

  /** 設定の項目名 → 画面に出す名前(基本設計書 §4.8)。 */
  const GROUPS: { title: string; items: { key: string; label: string }[] }[] = [
    {
      title: '基盤の色',
      items: [
        { key: 'bg', label: '背景' },
        { key: 'surface', label: 'カードの地' },
        { key: 'surface_alt', label: 'カードの地(薄い)' },
        { key: 'text', label: '文字(本文)' },
        { key: 'text_sub', label: '文字(副)' },
        { key: 'text_muted', label: '文字(薄い)' },
        { key: 'border', label: '罫線' },
        { key: 'border_strong', label: '罫線(濃い)' }
      ]
    },
    {
      title: '判定のラベル(背景と文字の組)',
      items: [
        { key: 'buy_bg', label: '買い・背景' },
        { key: 'buy_fg', label: '買い・文字' },
        { key: 'sell_bg', label: '売り・背景' },
        { key: 'sell_fg', label: '売り・文字' },
        { key: 'neutral_bg', label: '中立・背景' },
        { key: 'neutral_fg', label: '中立・文字' },
        { key: 'unknown_bg', label: '判定不能・背景' },
        { key: 'unknown_fg', label: '判定不能・文字' },
        { key: 'conflict_bg', label: '食い違い・背景' },
        { key: 'conflict_fg', label: '食い違い・文字' }
      ]
    },
    {
      title: 'チャートの面と市場区分',
      items: [
        { key: 'up', label: '増えた側(チャート)' },
        { key: 'down', label: '減った側(チャート)' },
        { key: 'prime', label: 'プライム' },
        { key: 'standard', label: 'スタンダード' },
        { key: 'growth', label: 'グロース' }
      ]
    }
  ];

  /** コントラスト比を見る組(基本設計書 §4.8.2)。 */
  const PAIRS: [string, string, string][] = [
    ['買い', 'buy_bg', 'buy_fg'],
    ['売り', 'sell_bg', 'sell_fg'],
    ['中立', 'neutral_bg', 'neutral_fg'],
    ['判定不能', 'unknown_bg', 'unknown_fg'],
    ['食い違い', 'conflict_bg', 'conflict_fg'],
    ['本文', 'bg', 'text'],
    ['副の文字', 'bg', 'text_sub'],
    ['薄い文字', 'bg', 'text_muted']
  ];

  let theme = $state<Theme>({});
  let overrides = $state<Theme>({});
  let copied = $state(false);

  onMount(async () => {
    // 既定の読み込みを待つ(レイアウトと同じ Promise を共有する)
    await init();
    theme = merged();
    overrides = loadOverrides();
  });

  function set(key: string, value: string) {
    overrides = { ...overrides, [key]: value };
    theme = { ...theme, [key]: value };
    saveOverrides(overrides);
  }

  function setInvestor(index: number, value: string) {
    const list = [...((theme.investors as string[]) ?? [])];
    list[index] = value;
    overrides = { ...overrides, investors: list };
    theme = { ...theme, investors: list };
    saveOverrides(overrides);
  }

  function resetOne(key: string) {
    const { [key]: _drop, ...rest } = overrides;
    overrides = rest;
    theme = { ...defaultsOf(), ...rest };
    saveOverrides(rest);
  }

  function resetAll() {
    overrides = {};
    theme = defaultsOf();
    saveOverrides({});
  }

  function value(key: string): string {
    const v = theme[key];
    return typeof v === 'string' ? v : '';
  }

  const changed = $derived(Object.keys(overrides).length);

  /** config.toml の [theme] に貼れる形(基本設計書 §5.7)。 */
  const asToml = $derived.by(() => {
    const lines = ['[theme]'];
    for (const key of Object.keys(CSS_VARS)) {
      const v = theme[key];
      if (typeof v === 'string') lines.push(`${key.padEnd(13)}= "${v}"`);
    }
    const investors = theme.investors;
    if (Array.isArray(investors)) {
      lines.push(`investors    = [${investors.map((c) => `"${c}"`).join(', ')}]`);
    }
    return lines.join('\n');
  });

  async function copy() {
    try {
      await navigator.clipboard.writeText(asToml);
      copied = true;
      setTimeout(() => (copied = false), 2000);
    } catch {
      copied = false;
    }
  }
</script>

<div class="row" style="margin: 10px 0">
  <h1>設定</h1>
  <div class="grow"></div>
  {#if changed}<span class="muted">この端末で {changed} 項目を上書き中</span>{/if}
  <button type="button" onclick={resetAll} disabled={!changed}>すべて既定に戻す</button>
</div>

<section class="card">
  <p class="sub" style="margin-top: 0">
    色の既定値は設定ファイル(<code>config.toml</code> の <code>[theme]</code>)にあります。
    この画面で変えられるのは<strong>この端末だけ</strong>で、すぐに画面へ反映されます。
    全端末に反映したいときは、下の書き出しを設定ファイルに貼ってサーバーを再起動してください。
  </p>
  <p class="muted">スプリント1はライトモードだけです。ダークモードは次のスプリント以降に足します。</p>
</section>

{#each GROUPS as group}
  <section class="card">
    <h2>{group.title}</h2>
    <div class="grid">
      {#each group.items as item}
        <div class="field">
          <span class="label">{item.label}</span>
          <input type="color" value={value(item.key)} oninput={(e) => set(item.key, (e.currentTarget as HTMLInputElement).value.toUpperCase())} aria-label={`${item.label} の色`} />
          <input type="text" value={value(item.key)} oninput={(e) => set(item.key, (e.currentTarget as HTMLInputElement).value)} aria-label={`${item.label} の色(16進数)`} style="width: 92px" />
          <button type="button" onclick={() => resetOne(item.key)} disabled={!(item.key in overrides)}>既定に戻す</button>
        </div>
      {/each}
    </div>
  </section>
{/each}

<section class="card">
  <h2>主体の色(6つ)</h2>
  <div class="grid">
    {#each INVESTOR_ORDER as key, i}
      <div class="field">
        <span class="label">{INVESTOR_LABEL[key]}</span>
        <input
          type="color"
          value={((theme.investors as string[]) ?? [])[i] ?? '#888888'}
          oninput={(e) => setInvestor(i, (e.currentTarget as HTMLInputElement).value.toUpperCase())}
          aria-label={`${INVESTOR_LABEL[key]} の色`}
        />
        <span class="muted">{((theme.investors as string[]) ?? [])[i] ?? '—'}</span>
      </div>
    {/each}
  </div>
</section>

<section class="card">
  <h2>コントラスト比</h2>
  <p class="muted">本文は 4.5:1 以上が目安です(基本設計書 §9)。下回っても保存は止めません。</p>
  <div class="scroll-x">
    <table>
      <thead><tr><th>組</th><th>背景</th><th>文字</th><th class="num">比</th><th>見本</th></tr></thead>
      <tbody>
        {#each PAIRS as [label, bgKey, fgKey]}
          {@const r = contrast(value(bgKey), value(fgKey))}
          <tr>
            <td>{label}</td>
            <td>{value(bgKey)}</td>
            <td>{value(fgKey)}</td>
            <td class="num" style="color: {r != null && r < 4.5 ? 'var(--up)' : 'inherit'}">
              {r == null ? '—' : dec(r, 2)}{#if r != null && r < 4.5}&nbsp;⚠{/if}
            </td>
            <td><span class="tag" style="background: {value(bgKey)}; color: {value(fgKey)}">{label}</span></td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</section>

<section class="card">
  <h2>設定ファイルへの書き出し</h2>
  <div class="row">
    <button type="button" onclick={copy}>{copied ? 'コピーしました' : 'クリップボードにコピー'}</button>
    <span class="muted">config.toml の <code>[theme]</code> を、これで置き換えてください</span>
  </div>
  <pre>{asToml}</pre>
</section>

<style>
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 8px; }
  .field { display: flex; align-items: center; gap: 8px; }
  .field .label { flex: 0 0 150px; font-size: 12px; color: var(--text-sub); }
  input[type='color'] { width: 44px; padding: 2px; }
  pre {
    background: var(--surface-alt);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 10px;
    overflow-x: auto;
    font-size: 12px;
  }
  code { background: var(--surface-alt); padding: 1px 4px; border-radius: 3px; }
</style>
