<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import Chart from '$lib/components/Chart.svelte';
	import { groupedBar } from '$lib/charts';

	let { dateFrom = '', dateTo = '' }: { dateFrom?: string; dateTo?: string } = $props();

	let data: any[] = $state([]);
	let loading = $state(true);

	async function load() {
		loading = true;
		const p = new URLSearchParams();
		if (dateFrom) p.set('date_from', dateFrom);
		if (dateTo) p.set('date_to', dateTo);
		try { data = await api.get(`/trends/lng-comparison?${p}`); }
		catch (e) { console.error(e); }
		loading = false;
	}

	onMount(load);
	$effect(() => { dateFrom; dateTo; load(); });

	function val(type: string, key: string): number {
		const r = data.find((d: any) => d.site_type === type);
		return r ? Math.round((r[key] || 0) * 100) / 100 : 0;
	}

	const cats = ['Gen Hours', 'Fuel Used (L)', 'Efficiency (L/Hr)', 'Buffer Days', 'Diesel Cost', 'Blackout Hr'];
	const keys = ['avg_gen_hr', 'avg_fuel', 'efficiency', 'avg_buffer', 'avg_cost', 'avg_blackout'];
</script>

{#if loading}
	<p class="text-sm" style="color: #65655e; py-4 text-center">Loading...</p>
{:else if data.length >= 2}
	<h2 class="text-lg font-black uppercase mt-6 mb-3 px-3 py-1" style="background: #383832; color: #feffd6;">REGULAR VS LNG COMPARISON</h2>
	<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
		{#each cats as cat, i}
			<Chart option={groupedBar(
				['Regular', 'LNG'],
				[
					{ name: cat, data: [val('Regular', keys[i]), val('LNG', keys[i])], color: i % 2 === 0 ? '#3b82f6' : '#8b5cf6' }
				],
				{ title: `${cat} — Regular vs LNG` }
			)} height="260px" guide={{ formula: `Side-by-side comparison of Regular vs LNG generators for <b>${cat}</b>.`, sources: [{ data: cat, file: 'Blackout Hr Excel', col: keys[i], method: 'AVG by site_type' }], reading: [{ color: 'blue', text: 'Blue/Purple bar = metric value per type' }, { color: 'green', text: 'Lower fuel/cost = better; higher buffer = better' }], explain: `Compares <b>diesel vs LNG</b> generator performance for ${cat}. Helps evaluate which fuel type is more efficient.` }} />
		{/each}
	</div>
	<div class="flex gap-4 mt-3 text-xs" style="color: #65655e;">
		<span>Regular: {data.find((d: any) => d.site_type === 'Regular')?.site_count || 0} sites</span>
		<span>LNG: {data.find((d: any) => d.site_type === 'LNG')?.site_count || 0} sites</span>
	</div>
{:else}
	<p class="text-sm" style="color: #65655e; py-4 text-center">Need both Regular and LNG site types for comparison.</p>
{/if}
