<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import Chart from '$lib/components/Chart.svelte';
	import { hbarChart } from '$lib/charts';

	const guides: Record<string, any> = {
		fuel_used: {
			formula: 'Total diesel liters consumed by each site on the <b>last reporting day</b>.',
			sources: [{ data: 'Fuel Used', file: 'Blackout Hr Excel', col: 'Daily Used', method: 'SUM per site' }],
			reading: [{ color: 'red', text: '🔴 Top sites = Biggest fuel consumers' }, { color: 'green', text: '🟢 Shorter bar = Less fuel used' }],
			explain: 'Like a <b>leaderboard</b> of fuel guzzlers. The longest bar drinks the most diesel. Target these sites for <b>efficiency audits</b>.',
		},
		gen_hours: {
			formula: 'Total generator run hours per site on <b>last reporting day</b>.',
			sources: [{ data: 'Gen Hours', file: 'Blackout Hr Excel', col: 'Gen Run Hr', method: 'SUM per site' }],
			reading: [{ color: 'red', text: '🔴 Long bar = Generator ran all day (likely severe blackout)' }, { color: 'green', text: '🟢 Short bar = Brief or no blackout' }],
			explain: 'Shows which sites had the <b>worst power outages</b>. Long bars = generators running most of the day.',
		},
		efficiency: {
			formula: 'Liters used ÷ Generator hours = <b>L/Hr</b> per site.',
			sources: [{ data: 'Efficiency', file: 'Blackout Hr Excel', col: 'Daily Used ÷ Gen Run Hr', method: 'AVG per site' }],
			reading: [{ color: 'red', text: '🔴 High L/Hr = Wasteful or faulty generator' }, { color: 'green', text: '🟢 Normal: 15-20 L/Hr for most models' }],
			explain: 'Like <b>km per liter</b> for a car. High numbers mean the generator burns too much fuel per hour — check for <b>leaks or theft</b>.',
		},
		cost: {
			formula: 'Total diesel liters × Fuel price = <b>MMK cost</b> over the period.',
			sources: [{ data: 'Diesel Cost', file: 'Blackout + Fuel Price', col: 'Daily Used × Price', method: 'SUM per site' }],
			reading: [{ color: 'red', text: '🔴 Highest cost = Budget priority' }, { color: 'amber', text: '🟡 Check if high cost = high sales (justified)' }],
			explain: 'Shows where the <b>money goes</b>. Top sites should be checked — is the cost justified by sales revenue?',
		},
		diesel_pct: {
			formula: '(Diesel cost ÷ Sales revenue) × 100 = <b>% of sales spent on diesel</b>.',
			sources: [{ data: 'Diesel %', file: 'All files', col: '(Liters × Price) ÷ Sales', method: 'SUM/SUM per site' }],
			reading: [{ color: 'green', text: '🟢 < 0.9% = Healthy' }, { color: 'amber', text: '🟡 0.9-1.5% = Watch' }, { color: 'red', text: '🔴 > 3% = Diesel eating into profits' }],
			explain: 'If a store makes 10M in sales but spends 500K on diesel, that\'s 5% — <b class="text-red-400">too high</b>. Below 1% is ideal.',
		},
	};

	let { dateFrom = '', dateTo = '', sector = '' }: { dateFrom?: string; dateTo?: string; sector?: string } = $props();

	let data: Record<string, any[]> = $state({});
	let loading = $state(true);

	const metrics = [
		{ key: 'fuel_used', title: 'Top 15 — Fuel Used (L) Last Day', color: '#ef4444', valKey: 'fuel_used' },
		{ key: 'gen_hours', title: 'Top 15 — Generator Hours Last Day', color: '#3b82f6', valKey: 'gen_hours' },
		{ key: 'efficiency', title: 'Top 15 — Efficiency (L/Hr) Last Day', color: '#8b5cf6', valKey: 'efficiency' },
		{ key: 'cost', title: 'Top 15 — Diesel Cost (MMK)', color: '#f59e0b', valKey: 'cost' },
		{ key: 'diesel_pct', title: 'Top 15 — Diesel % of Sales', color: '#ec4899', valKey: 'diesel_pct' },
	];

	async function load() {
		loading = true;
		const p = new URLSearchParams();
		if (dateFrom) p.set('date_from', dateFrom);
		if (dateTo) p.set('date_to', dateTo);
		if (sector) p.set('sector', sector);
		try {
			const results = await Promise.all(
				metrics.map(m => api.get(`/rankings/${m.key}?${p}&limit=15`))
			);
			metrics.forEach((m, i) => data[m.key] = results[i]);
		} catch (e) { console.error(e); }
		loading = false;
	}

	onMount(load);
	$effect(() => { dateFrom; dateTo; sector; load(); });

	function colors(vals: number[], metric: string): string[] {
		if (metric === 'diesel_pct') return vals.map(v => v > 3 ? '#ef4444' : v > 1.5 ? '#f59e0b' : v > 0.9 ? '#eab308' : '#22c55e');
		if (metric === 'efficiency') return vals.map(v => v > 20 ? '#ef4444' : v > 15 ? '#f59e0b' : '#22c55e');
		const max = Math.max(...vals);
		return vals.map(v => {
			const pct = max > 0 ? v / max : 0;
			return pct > 0.8 ? '#ef4444' : pct > 0.5 ? '#f59e0b' : '#3b82f6';
		});
	}
</script>

{#if loading}
	<p class="text-sm py-4 text-center" style="color: #65655e;">Loading rankings...</p>
{:else}
	<h2 class="text-lg font-black uppercase mt-6 mb-3 px-3 py-1" style="background: #383832; color: #feffd6;">SITE RANKINGS</h2>

	<!-- Last Day Rankings -->
	<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
		{#each metrics.slice(0, 3) as m}
			{@const d = data[m.key] || []}
			{#if d.length > 0}
				<Chart option={hbarChart(
					d.map((r: any) => r.site_id),
					d.map((r: any) => Math.round((r[m.valKey] || 0) * 100) / 100),
					{ title: m.title, colors: colors(d.map((r: any) => r[m.valKey] || 0), m.key) }
				)} height="{Math.max(300, d.length * 28)}px" guide={guides[m.key] || null} />
			{/if}
		{/each}
	</div>

	<!-- Period Rankings -->
	<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
		{#each metrics.slice(3) as m}
			{@const d = data[m.key] || []}
			{#if d.length > 0}
				<Chart option={hbarChart(
					d.map((r: any) => r.site_id),
					d.map((r: any) => Math.round((r[m.valKey] || 0) * 100) / 100),
					{ title: m.title, colors: colors(d.map((r: any) => r[m.valKey] || 0), m.key) }
				)} height="{Math.max(300, d.length * 28)}px" guide={guides[m.key] || null} />
			{/if}
		{/each}
	</div>
{/if}
