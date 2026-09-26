<script lang="ts">
  /** 判定の札。色だけで区別しないよう、必ず文字のラベルを出す(基本設計書 §4.8)。 */
  import { VERDICT_LABEL, VERDICT_VARS } from '../labels';
  let { verdict = null as string | null } = $props();
  const key = $derived(verdict && VERDICT_VARS[verdict] ? verdict : 'unknown');
</script>

<span
  class="tag"
  class:tag--unknown={key === 'unknown'}
  style="background: {VERDICT_VARS[key].bg}; color: {VERDICT_VARS[key].fg}"
>{VERDICT_LABEL[key] ?? '判定不能'}</span>
