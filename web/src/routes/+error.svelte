<script lang="ts">
  import { page } from '$app/state';
</script>

<div class="card">
  <h2>{page.status === 404 ? 'ページが見つかりません' : '表示できません'}</h2>
  <p class="sub">
    {#if page.status === 404}
      URL をお確かめください。
    {:else}
      時間をおいて開き直してください。
    {/if}
  </p>
  <p><a href="/market">市場概況へ</a></p>
</div>
