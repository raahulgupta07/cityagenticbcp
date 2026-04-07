<script lang="ts">
	import { api } from '$lib/api';

	let { kpiData = null, heatmapData = [], siteData = null }:
		{ kpiData?: any; heatmapData?: any[]; siteData?: any } = $props();

	let insights: Record<string, string> = $state({});
	let loading: Record<string, boolean> = $state({});

	async function fetchInsight(type: string, data: any) {
		if (loading[type]) return;
		loading[type] = true;
		try {
			const res = await api.post('/insights', { type, data, force_refresh: false });
			insights[type] = res.content || 'No insight available.';
		} catch (e: any) {
			insights[type] = `Error: ${e.message}`;
		}
		loading[type] = false;
	}

	function briefingData() {
		if (!kpiData) return {};
		return {
			total_sites: kpiData.total || 0,
			critical_sites: kpiData.crit || 0,
			warning_sites: kpiData.warn || 0,
			safe_sites: kpiData.safe || 0,
			total_tank: kpiData.tank || 0,
			avg_burn: kpiData.burn || 0,
			avg_buffer: kpiData.buffer || 0,
		};
	}

	function kpiPayload() {
		if (!kpiData) return {};
		return {
			buffer: kpiData.buffer || 0,
			tank: kpiData.tank || 0,
			burn: kpiData.burn || 0,
			critical: kpiData.crit || 0,
			warning: kpiData.warn || 0,
			safe: kpiData.safe || 0,
			cost: kpiData.cost || 0,
		};
	}

	function tableSummary() {
		if (!heatmapData || heatmapData.length === 0) return '';
		return heatmapData.map((r: any) =>
			`${r.sector_id}: ${r.total_sites} sites, buffer ${r.buffer_days ?? '?'}d, blackout ${r.blackout_hr ?? '?'}hr, fuel ${r.avg_fuel ?? '?'}L`
		).join(' | ');
	}

	const buttons = [
		{ type: 'briefing', label: 'Morning Briefing', icon: '☀️', desc: 'Executive summary of current state', getData: briefingData },
		{ type: 'kpi', label: 'KPI Insight', icon: '📊', desc: 'Interpret the KPI numbers', getData: kpiPayload },
		{ type: 'table', label: 'Table Insight', icon: '🗺️', desc: 'Analyze sector heatmap', getData: () => ({ summary: tableSummary(), table_type: 'sector' }) },
	];
</script>

<div class="mt-6">
	<h2 class="text-lg font-black uppercase mb-3" style="color: #383832;">🧠 AI Insights</h2>
	<p class="text-xs mb-4" style="color: #65655e;">Powered by Gemini 3.1 Flash Lite. Cached for 6 hours. Click to generate.</p>

	<div class="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
		{#each buttons as btn}
			<button
				onclick={() => fetchInsight(btn.type, btn.getData())}
				disabled={loading[btn.type]}
				class="p-4 text-left transition group"
				style="background: white; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;"
			>
				<div class="flex items-center gap-2 mb-1">
					<span class="text-lg">{btn.icon}</span>
					<span class="text-sm font-bold transition" style="color: #383832;">{btn.label}</span>
				</div>
				<p class="text-[10px]" style="color: #65655e;">{btn.desc}</p>
				{#if loading[btn.type]}
					<div class="mt-2 text-xs animate-pulse" style="color: #006f7c;">Generating...</div>
				{/if}
			</button>
		{/each}
	</div>

	<!-- Site Insight (separate — needs site selection) -->
	{#if siteData}
		<button
			onclick={() => fetchInsight('site', siteData)}
			disabled={loading['site']}
			class="w-full p-4 text-left transition group mb-4"
			style="background: white; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;"
		>
			<div class="flex items-center gap-2 mb-1">
				<span class="text-lg">📍</span>
				<span class="text-sm font-bold transition" style="color: #383832;">Site Insight — {siteData.site_id}</span>
			</div>
			<p class="text-[10px]" style="color: #65655e;">Deep-dive analysis for this specific site</p>
			{#if loading['site']}
				<div class="mt-2 text-xs animate-pulse" style="color: #006f7c;">Generating...</div>
			{/if}
		</button>
	{/if}

	<!-- Display insights -->
	{#each Object.entries(insights) as [type, content]}
		<div class="p-5 mb-3" style="background: #f6f4e9; border: 2px solid #007518;">
			<div class="flex items-center gap-2 mb-2">
				<span class="text-xs font-black uppercase" style="color: #007518;">
					{type === 'briefing' ? '☀️ Morning Briefing' : type === 'kpi' ? '📊 KPI Analysis' : type === 'table' ? '🗺️ Sector Analysis' : '📍 Site Analysis'}
				</span>
			</div>
			<div class="text-sm leading-relaxed whitespace-pre-wrap" style="color: #383832;">{content}</div>
		</div>
	{/each}
</div>
