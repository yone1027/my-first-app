<script lang="ts">
  /** 各画面に常に出す注意書き(要件 R6)。 */
  import { CAUTIONS } from '../labels';
  let { extra = [] as string[] } = $props();
</script>

<div class="cautions">
  <ul>
    {#each [...CAUTIONS, ...extra] as line}
      <li>{line}</li>
    {/each}
  </ul>
</div>
