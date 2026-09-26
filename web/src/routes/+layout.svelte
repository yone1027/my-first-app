<script lang="ts">
  import '$lib/app.css';
  import { onMount } from 'svelte';
  import Header from '$lib/components/Header.svelte';
  import { api, type Status } from '$lib/api';
  import * as theme from '$lib/theme';

  let { children } = $props();
  let status = $state<Status | null>(null);

  onMount(async () => {
    await theme.init();
    // この API はページを開くたびに1回だけ呼ぶ。自動では呼び直さない(§5.7)
    try {
      status = await api.status();
    } catch {
      status = null;
    }
  });
</script>

<Header {status} />
<main class="page">
  {@render children()}
</main>
