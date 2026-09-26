<script lang="ts">
  /** お金の流れの階層ナビ(要件 F1-6)。①日本市場 → ②市場区分 → ③業種。 */
  let { at = 1, period = '13w', scope = 'all' } = $props();
  const steps = [
    { n: 1, label: '① 日本市場', href: `/market?period=${period}` },
    { n: 2, label: '② 市場区分', href: `/market/segments?period=${period}` },
    { n: 3, label: '③ 業種', href: `/market/sectors?period=${period}&scope=${scope}` }
  ];
</script>

<nav class="row" style="gap: 4px" aria-label="お金の流れの階層">
  {#each steps as step, i}
    {#if i > 0}<span class="muted">›</span>{/if}
    {#if step.n === at}
      <span class="here" aria-current="step">{step.label}</span>
    {:else}
      <a href={step.href}>{step.label}</a>
    {/if}
  {/each}
</nav>

<style>
  .here { font-weight: 700; }
  nav a { text-decoration: none; color: var(--text-sub); }
</style>
