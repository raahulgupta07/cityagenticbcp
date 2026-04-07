<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import * as echarts from 'echarts';

	let { dates = [], values = [], color = '#007518', height = '60px', areaOpacity = 0.15, good = 'low' }: {
		dates?: string[];
		values?: number[];
		color?: string;
		height?: string;
		areaOpacity?: number;
		good?: string;
	} = $props();

	let container: HTMLDivElement;
	let chart: echarts.ECharts | null = null;

	function buildOption() {
		const lastVal = values[values.length - 1] || 0;
		const prevVal = values[values.length - 2] || 0;
		const trending = lastVal > prevVal ? 'up' : lastVal < prevVal ? 'down' : 'flat';
		const endColor = trending === 'up'
			? (good === 'high' ? '#007518' : '#be2d06')
			: trending === 'down'
				? (good === 'high' ? '#be2d06' : '#007518')
				: '#828179';

		return {
			backgroundColor: 'transparent',
			grid: { top: 4, right: 4, bottom: 16, left: 4 },
			xAxis: {
				type: 'category',
				data: dates.map(d => d.slice(5)),
				show: true,
				axisLine: { show: false },
				axisTick: { show: false },
				axisLabel: { fontSize: 8, color: '#9d9d91', fontFamily: 'Space Grotesk, monospace' },
			},
			yAxis: {
				type: 'value',
				show: false,
				min: (v: any) => v.min - (v.max - v.min) * 0.1,
			},
			tooltip: {
				trigger: 'axis',
				backgroundColor: '#383832',
				borderColor: '#383832',
				textStyle: { color: '#feffd6', fontSize: 10, fontFamily: 'Space Grotesk, monospace' },
				formatter: (p: any) => {
					const v = p[0];
					return `<b>${v.name}</b><br/>${v.value?.toLocaleString()}`;
				},
			},
			series: [{
				type: 'line',
				data: values,
				smooth: true,
				symbol: 'circle',
				symbolSize: (val: number, params: any) => params.dataIndex === values.length - 1 ? 8 : 4,
				itemStyle: {
					color: (params: any) => params.dataIndex === values.length - 1 ? endColor : color,
					borderColor: 'white',
					borderWidth: 1,
				},
				lineStyle: { color, width: 2 },
				areaStyle: {
					color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
						{ offset: 0, color: color + '40' },
						{ offset: 1, color: color + '05' },
					]),
				},
			}],
		};
	}

	onMount(() => {
		if (container && values.length > 0) {
			chart = echarts.init(container, undefined, { renderer: 'canvas' });
			chart.setOption(buildOption());
			const ro = new ResizeObserver(() => chart?.resize());
			ro.observe(container);
			return () => ro.disconnect();
		}
	});

	onDestroy(() => {
		chart?.dispose();
	});

	$effect(() => {
		if (chart && values.length > 0) {
			chart.setOption(buildOption(), true);
		}
	});
</script>

<div bind:this={container} style="width: 100%; height: {height};"></div>
