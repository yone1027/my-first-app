<script lang="ts">
  /** ECharts の入れ物(詳細設計書 §8.4)。色は CSS 変数から読む。 */
  import { onMount } from 'svelte';
  import * as echarts from 'echarts';

  // ECharts の option は入れ子が深く、部分的な組み立てでは型が合わないので緩く受ける
  let { option = {} as Record<string, unknown>, height = 260 } = $props();
  let box: HTMLDivElement;
  let chart: echarts.ECharts | null = null;

  onMount(() => {
    chart = echarts.init(box, null, { renderer: 'canvas' });
    const observer = new ResizeObserver(() => chart?.resize());
    observer.observe(box);
    return () => {
      observer.disconnect();
      chart?.dispose();
      chart = null;
    };
  });

  $effect(() => {
    // option が変わるたびに描き直す(notMerge で前の系列を残さない)
    chart?.setOption(option as echarts.EChartsOption, true);
  });
</script>

<div bind:this={box} style="width: 100%; height: {height}px"></div>
