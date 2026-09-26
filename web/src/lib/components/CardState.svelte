<script lang="ts">
  /** カードごとの部分失敗(詳細設計書 §8.2)。1つ欠けても他は出す。 */
  let { error = null as string | null, empty = false, emptyText = 'この週のデータはありません' } = $props();
</script>

{#if error}
  <p class="notice">データを読み込めませんでした<br /><span class="muted">{error}</span></p>
{:else if empty}
  <p class="notice">{emptyText}</p>
{/if}
