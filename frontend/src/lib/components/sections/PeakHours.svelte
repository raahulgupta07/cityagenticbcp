<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';

	let { siteId = '' }: { siteId?: string } = $props();

	let data: any = $state({ heatmap: [], has_data: false, cost_per_hr: 0 });
	let loading = $state(true);

	async function load() {
		if (!siteId) return;
		loading = true;
		try { data = await api.get(`/site/${siteId}/peak-hours`); }
		catch (e) { console.error(e); }
		loading = false;
	}

	onMount(load);
	$effect(() => { siteId; load(); });

	const hours = Array.from({ length: 24 }, (_, i) => i);
	const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

	function cell(dow: number, hour: number) {
		return data.heatmap.find((c: any) => c.dow === dow && c.hour === hour);
	}

	function icon(status: string) {
		if (status === 'PEAK') return '🟢';
		if (status === 'PROFITABLE') return '🟡';
		if (status === 'MARGINAL') return '🟠';
		return '🔴';
	}

	function fmt(v: number) { return v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(0)+'K' : v.toFixed(0); }
</script>

{#if loading}
	<p class="text-sm py-4 text-center" style="color: #65655e;">Loading peak hours...</p>
{:else if !data.has_data}
	<p class="text-sm py-4 text-center" style="color: #65655e;">No hourly sales data for this site.</p>
{:else}
	<h3 class="text-sm font-black uppercase mb-2" style="color: #383832;">⏰ Peak Hours Heatmap</h3>
	<p class="text-xs mb-3" style="color: #65655e;">Cost/Hr: {fmt(data.cost_per_hr)} MMK. 🟢 PEAK (&gt;3x) 🟡 PROFITABLE (&gt;1.5x) 🟠 MARGINAL (&gt;1x) 🔴 LOSING (&lt;1x)</p>

	<div class="overflow-x-auto">
		<table class="text-[10px] border-collapse" style="border: 1px solid #383832;">
			<thead>
				<tr style="background: #ebe8dd;">
					<th class="px-2 py-1 font-black uppercase" style="color: #65655e; border-bottom: 2px solid #383832;">Hr</th>
					{#each days as d}
						<th class="px-3 py-1 font-black uppercase" style="color: #383832; border-bottom: 2px solid #383832;">{d}</th>
					{/each}
				</tr>
			</thead>
			<tbody>
				{#each hours as h, i}
					<tr style="background: {i % 2 === 0 ? 'white' : '#f6f4e9'}; border-bottom: 1px solid #ebe8dd;">
						<td class="px-2 py-0.5 font-mono" style="color: #65655e;">{h.toString().padStart(2, '0')}:00</td>
						{#each [0, 1, 2, 3, 4, 5, 6] as dow}
							{@const c = cell(dow, h)}
							<td class="px-3 py-0.5 text-center" title={c ? `Sales: ${fmt(c.avg_sales)}, Profit: ${c.profitability.toFixed(1)}x` : ''}>
								{c ? icon(c.status) : '⚪'}
							</td>
						{/each}
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{/if}
