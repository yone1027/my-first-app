<script lang="ts">
  /** 期間(13週・26週・52週)。既定は13週。次の画面にも引き継ぐ(基本設計書 §4.4)。 */
  import { PERIODS } from '../labels';
  let { period = '13w', onpick = (_: string) => {} } = $props();
</script>

<div class="row" style="gap: 6px">
  <span class="muted">期間(次の画面にも引き継ぐ)</span>
  {#each PERIODS as p}
    <button type="button" aria-pressed={period === p.key} onclick={() => onpick(p.key)}>{p.label}</button>
  {/each}
</div>
