<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import * as echarts from 'echarts';

	let { option, height = '380px', guide }: {
		option: any;
		height?: string;
		guide?: { formula: string; sources: { data: string; file: string; col: string; method: string }[]; reading: { color: string; text: string }[]; explain: string } | null;
	} = $props();

	const chartId = crypto.randomUUID();

	let container: HTMLDivElement;
	let fullContainer: HTMLDivElement;
	let chart: echarts.ECharts | null = null;
	let fullChart: echarts.ECharts | null = null;
	let showGuide = $state(false);
	let showFull = $state(false);

	const ANALOG_THEME = {
		backgroundColor: '#feffd6',
		textStyle: { color: '#383832', fontFamily: 'Space Grotesk, monospace' },
		title: { textStyle: { color: '#383832', fontWeight: 900 }, subtextStyle: { color: '#65655e' } },
		legend: { textStyle: { color: '#383832' } },
		categoryAxis: {
			axisLine: { lineStyle: { color: '#383832' } },
			axisTick: { lineStyle: { color: '#383832' } },
			axisLabel: { color: '#65655e' },
			splitLine: { lineStyle: { color: 'rgba(56,56,50,0.12)' } },
		},
		valueAxis: {
			axisLine: { lineStyle: { color: '#383832' } },
			axisTick: { lineStyle: { color: '#383832' } },
			axisLabel: { color: '#65655e' },
			splitLine: { lineStyle: { color: 'rgba(56,56,50,0.12)' } },
		},
		tooltip: {
			backgroundColor: '#383832', borderColor: '#383832', borderWidth: 2,
			textStyle: { color: '#feffd6', fontFamily: 'Space Grotesk, monospace', fontSize: 11 },
		},
		color: ['#007518', '#006f7c', '#9d4867', '#ff9d00', '#be2d06', '#383832', '#4a9c5d', '#3d8f9a', '#c06a85', '#ffb733'],
	};

	let themeRegistered = false;
	function ensureTheme() {
		if (!themeRegistered) {
			try { echarts.registerTheme('analog', ANALOG_THEME); } catch {}
			themeRegistered = true;
		}
	}

	const guideColors: Record<string, string> = {
		green: 'color: #007518', amber: 'color: #ff9d00', red: 'color: #be2d06',
		blue: 'color: #006f7c', orange: 'color: #ff9d00'
	};

	const badgeBg: Record<string, string> = {
		SUM: '#ff9d00', AVG: '#9d4867', LATEST: '#006f7c', COUNT: '#007518'
	};

	function getBadge(method: string): string {
		for (const [key, color] of Object.entries(badgeBg)) {
			if (method.toUpperCase().includes(key)) return color;
		}
		return '#ff9d00';
	}

	const chartTitle = $derived(option?.title?.text || option?.title?.[0]?.text || '');

	onMount(() => {
		ensureTheme();
		chart = echarts.init(container, 'analog');
		chart.setOption(option);
		const ro = new ResizeObserver(() => chart?.resize());
		ro.observe(container);
		return () => ro.disconnect();
	});

	$effect(() => {
		if (chart && option) chart.setOption(option, true);
	});

	function openFull() {
		showFull = true;
		setTimeout(() => {
			if (fullContainer) {
				ensureTheme();
				fullChart = echarts.init(fullContainer, 'analog');
				// Enhanced option with toolbox + dataZoom for fullscreen
				const fullOption = { ...option };
				fullChart.setOption(fullOption);
			}
		}, 50);
	}

	function closeFull() {
		fullChart?.dispose();
		fullChart = null;
		showFull = false;
	}

	onDestroy(() => { chart?.dispose(); fullChart?.dispose(); });
</script>

<!-- Chart wrapper with toolbar -->
<div class="relative group" id="chart-{chartId}" data-chart-id={chartId}>
	<!-- Chart definition bar -->
	{#if guide}
		<div class="px-3 py-1.5 text-[10px] font-mono" style="background: #ebe8dd; border: 2px solid #383832; border-bottom: 0; color: #383832; line-height: 1.5;">
			<span class="font-black" style="color: #006f7c;">FORMULA:</span> <span>{@html guide.formula}</span>
			{#if guide.reading && guide.reading.length > 0}
				<span class="ml-3 font-black" style="color: #65655e;">|</span>
				{#each guide.reading as r}
					<span class="ml-2">{r.text}</span>
				{/each}
			{/if}
		</div>
	{/if}
	<!-- Chart -->
	<div bind:this={container} style="width:100%;height:{height};border:2px solid #383832; cursor: pointer;"
		onclick={openFull} role="button" tabindex="0" onkeydown={(e) => { if (e.key === 'Enter') openFull(); }}></div>

	<!-- Toolbar (top-right, visible on hover) -->
	<div class="absolute top-1 right-1 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
		{#if guide}
			<button onclick={(e) => { e.stopPropagation(); showGuide = !showGuide; }}
				class="w-6 h-6 flex items-center justify-center text-[10px] font-black"
				style="background: #383832; color: #feffd6; border: 1px solid #383832;"
				title="Chart Guide">ℹ</button>
		{/if}
		<button onclick={(e) => { e.stopPropagation(); openFull(); }}
			class="w-6 h-6 flex items-center justify-center"
			style="background: #383832; color: #feffd6; border: 1px solid #383832;"
			title="Full Screen">
			<span class="material-symbols-outlined text-xs">fullscreen</span>
		</button>
	</div>
</div>

<!-- Guide Popup Modal -->
{#if guide && showGuide}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="fixed inset-0 z-[200] flex items-center justify-center" style="background: rgba(0,0,0,0.5);"
		onclick={() => showGuide = false}>
		<div class="w-[500px] max-h-[80vh] overflow-y-auto" style="background: #feffd6; border: 3px solid #383832; box-shadow: 6px 6px 0px 0px #383832;"
			onclick={(e) => e.stopPropagation()}>
			<!-- Header -->
			<div class="px-4 py-3 flex justify-between items-center" style="background: #383832; color: #feffd6;">
				<div>
					{#if chartTitle}<div class="text-base font-black" style="color: #00fc40;">{chartTitle}</div>{/if}
					<div class="text-[10px] uppercase opacity-75">CHART_DEFINITION</div>
					<div class="text-[8px] font-mono opacity-50 mt-0.5">ID: {chartId}</div>
				</div>
				<button onclick={() => showGuide = false} class="font-black text-lg">✕</button>
			</div>

			<div class="p-5 text-[11px] font-mono space-y-4">
				<!-- Formula -->
				<div>
					<div class="font-black uppercase text-xs mb-1 px-2 py-0.5 inline-block" style="background: #006f7c; color: #feffd6;">FORMULA</div>
					<div class="mt-1 p-3" style="background: white; border: 1px solid #383832; color: #383832;">{@html guide.formula}</div>
				</div>

				<!-- Data Source -->
				<div>
					<div class="font-black uppercase text-xs mb-1 px-2 py-0.5 inline-block" style="background: #007518; color: #feffd6;">DATA_SOURCE</div>
					<div class="mt-1" style="border: 1px solid #383832;">
						<div class="grid grid-cols-[1fr_1fr_1fr_auto] gap-0 text-[9px] font-black uppercase" style="background: #ebe8dd; border-bottom: 1px solid #383832;">
							<span class="px-2 py-1">Data</span><span class="px-2 py-1">File</span><span class="px-2 py-1">Column</span><span class="px-2 py-1">Method</span>
						</div>
						{#each guide.sources as src, si}
							<div class="grid grid-cols-[1fr_1fr_1fr_auto] gap-0" style="background: {si % 2 ? '#f6f4e9' : 'white'}; border-bottom: 1px solid #ebe8dd;">
								<span class="px-2 py-1.5" style="color: #006f7c;">{src.data}</span>
								<span class="px-2 py-1.5" style="color: #007518;">{src.file}</span>
								<span class="px-2 py-1.5" style="color: #006f7c;">{src.col}</span>
								<span class="px-2 py-1.5"><span class="px-1 py-0.5 text-[8px] font-black" style="background: {getBadge(src.method)}; color: #feffd6;">{src.method}</span></span>
							</div>
						{/each}
					</div>
				</div>

				<!-- How to Read -->
				<div>
					<div class="font-black uppercase text-xs mb-1 px-2 py-0.5 inline-block" style="background: #ff9d00; color: #383832;">HOW_TO_READ</div>
					<div class="mt-1 p-3 space-y-1" style="background: white; border: 1px solid #383832;">
						{#each guide.reading as r}
							<div style="{guideColors[r.color] || 'color: #383832'}">{r.text}</div>
						{/each}
					</div>
				</div>

				<!-- Simple Explanation -->
				<div>
					<div class="font-black uppercase text-xs mb-1 px-2 py-0.5 inline-block" style="background: #9d4867; color: #feffd6;">SIMPLE_EXPLANATION</div>
					<div class="mt-1 p-3" style="background: white; border: 1px solid #383832; color: #383832; line-height: 1.6;">{@html guide.explain}</div>
				</div>
			</div>
		</div>
	</div>
{/if}

<!-- Full Screen Modal: Chart left + Guide right -->
{#if showFull}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="fixed inset-0 z-[200] flex items-center justify-center" style="background: rgba(0,0,0,0.7);"
		onclick={closeFull}>
		<div class="w-[95vw] h-[85vh] flex relative" style="border: 3px solid #383832; box-shadow: 6px 6px 0px 0px #383832;"
			onclick={(e) => e.stopPropagation()}>
			<!-- Close button -->
			<button onclick={closeFull}
				class="absolute top-2 right-2 z-10 w-8 h-8 flex items-center justify-center font-black text-lg"
				style="background: #383832; color: #feffd6;">✕</button>

			<!-- Left: Chart -->
			<div class="{guide ? 'w-[70%]' : 'w-full'} h-full" style="background: #feffd6;">
				<div bind:this={fullContainer} style="width:100%;height:100%;"></div>
			</div>

			<!-- Right: Guide Panel -->
			{#if guide}
				<div class="w-[30%] h-full overflow-y-auto" style="background: #f6f4e9; border-left: 3px solid #383832;">
					<!-- Guide Header -->
					<div class="px-4 py-3" style="background: #383832; color: #feffd6;">
						<div class="font-black uppercase text-sm">CHART_DEFINITION</div>
						{#if chartTitle}<div class="text-[10px] opacity-75 mt-0.5">{chartTitle}</div>{/if}
						<div class="text-[8px] font-mono opacity-50 mt-0.5">ID: {chartId}</div>
					</div>

					<div class="p-4 text-[11px] font-mono space-y-4">
						<!-- Formula -->
						<div>
							<div class="font-black uppercase text-xs mb-1 px-2 py-0.5 inline-block" style="background: #006f7c; color: #feffd6;">FORMULA</div>
							<div class="mt-1 p-3" style="background: white; border: 1px solid #383832; color: #383832;">{@html guide.formula}</div>
						</div>

						<!-- Data Source -->
						<div>
							<div class="font-black uppercase text-xs mb-1 px-2 py-0.5 inline-block" style="background: #007518; color: #feffd6;">DATA_SOURCE</div>
							<div class="mt-1" style="border: 1px solid #383832;">
								<div class="grid grid-cols-[1fr_1fr_1fr_auto] gap-0 text-[9px] font-black uppercase" style="background: #ebe8dd; border-bottom: 1px solid #383832;">
									<span class="px-2 py-1">Data</span><span class="px-2 py-1">File</span><span class="px-2 py-1">Column</span><span class="px-2 py-1">Method</span>
								</div>
								{#each guide.sources as src, si}
									<div class="grid grid-cols-[1fr_1fr_1fr_auto] gap-0" style="background: {si % 2 ? '#f6f4e9' : 'white'}; border-bottom: 1px solid #ebe8dd;">
										<span class="px-2 py-1.5" style="color: #006f7c;">{src.data}</span>
										<span class="px-2 py-1.5" style="color: #007518;">{src.file}</span>
										<span class="px-2 py-1.5" style="color: #006f7c;">{src.col}</span>
										<span class="px-2 py-1.5"><span class="px-1 py-0.5 text-[8px] font-black" style="background: {getBadge(src.method)}; color: #feffd6;">{src.method}</span></span>
									</div>
								{/each}
							</div>
						</div>

						<!-- How to Read -->
						<div>
							<div class="font-black uppercase text-xs mb-1 px-2 py-0.5 inline-block" style="background: #ff9d00; color: #383832;">HOW_TO_READ</div>
							<div class="mt-1 p-3 space-y-1" style="background: white; border: 1px solid #383832;">
								{#each guide.reading as r}
									<div style="{guideColors[r.color] || 'color: #383832'}">{r.text}</div>
								{/each}
							</div>
						</div>

						<!-- Simple Explanation -->
						<div>
							<div class="font-black uppercase text-xs mb-1 px-2 py-0.5 inline-block" style="background: #9d4867; color: #feffd6;">SIMPLE_EXPLANATION</div>
							<div class="mt-1 p-3" style="background: white; border: 1px solid #383832; color: #383832; line-height: 1.6;">{@html guide.explain}</div>
						</div>
					</div>
				</div>
			{/if}
		</div>
	</div>
{/if}
