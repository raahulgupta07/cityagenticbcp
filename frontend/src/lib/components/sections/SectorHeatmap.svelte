<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';

	let { dateFrom = '', dateTo = '' }: { dateFrom?: string; dateTo?: string } = $props();

	let rows: any[] = $state([]);
	let loading = $state(true);

	async function load() {
		loading = true;
		try {
			const p = new URLSearchParams();
			if (dateFrom) p.set('date_from', dateFrom);
			if (dateTo) p.set('date_to', dateTo);
			rows = await api.get(`/sector-heatmap?${p}`);
		} catch (e) { console.error(e); }
		loading = false;
	}

	onMount(load);
	$effect(() => { dateFrom; dateTo; load(); });

	function fmt(v: number | null) {
		if (v === null || v === undefined) return '—';
		return v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(1)+'K' : v.toLocaleString(undefined, { maximumFractionDigits: 1 });
	}
</script>

{#if loading}
	<p class="text-sm py-4 text-center" style="color: #65655e;">Loading heatmap...</p>
{:else if rows.length > 0}
	<h2 class="text-lg font-black uppercase mt-6 mb-3" style="color: #383832;">🗺️ Sector Heatmap</h2>
	<div class="overflow-hidden" style="background: white; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
		<div class="overflow-x-auto">
			<table class="w-full text-xs">
				<thead>
					<tr style="background: #ebe8dd;">
						<th class="text-left py-3 px-4 font-black uppercase" style="color: #383832; border-bottom: 2px solid #383832;">Sector</th>
						<th class="text-left py-3 px-3 font-black uppercase" style="color: #383832; border-bottom: 2px solid #383832;">Sites</th>
						<th class="text-center py-3 px-3 font-black uppercase" style="color: #383832; border-bottom: 2px solid #383832;">Diesel Price</th>
						<th class="text-center py-3 px-3 font-black uppercase" style="color: #383832; border-bottom: 2px solid #383832;">Blackout Hr</th>
						<th class="text-center py-3 px-3 font-black uppercase" style="color: #383832; border-bottom: 2px solid #383832;">Buffer Days</th>
						<th class="text-center py-3 px-3 font-black uppercase" style="color: #383832; border-bottom: 2px solid #383832;">Diesel %</th>
						<th class="text-center py-3 px-3 font-black uppercase" style="color: #383832; border-bottom: 2px solid #383832;">Avg Fuel (L)</th>
						<th class="text-center py-3 px-3 font-black uppercase" style="color: #383832; border-bottom: 2px solid #383832;">Avg Gen Hr</th>
						<th class="text-center py-3 px-2 font-black uppercase" style="color: #be2d06; border-bottom: 2px solid #383832;">Crit</th>
						<th class="text-center py-3 px-2 font-black uppercase" style="color: #ff9d00; border-bottom: 2px solid #383832;">Warn</th>
						<th class="text-center py-3 px-2 font-black uppercase" style="color: #007518; border-bottom: 2px solid #383832;">Safe</th>
					</tr>
				</thead>
				<tbody>
					{#each rows as r, i}
						<tr onclick={() => window.location.href = '/dashboard?sector=' + r.sector_id}
							class="cursor-pointer hover:bg-[#ebe8dd] transition-colors"
							style="background: {i % 2 === 0 ? 'white' : '#f6f4e9'}; border-bottom: 1px solid #ebe8dd;">
							<td class="py-2.5 px-4 font-bold" style="color: #383832;">{r.sector_id}</td>
							<td class="py-2.5 px-3" style="color: #383832;">{r.total_sites}</td>
							<td class="py-2.5 px-3 text-center">
								<span class="mr-1">{r.diesel_price_icon}</span>
								<span style="color: #383832;">{fmt(r.diesel_price)}</span>
							</td>
							<td class="py-2.5 px-3 text-center">
								<span class="mr-1">{r.blackout_icon}</span>
								<span style="color: #383832;">{r.blackout_hr !== null ? r.blackout_hr : '—'}</span>
							</td>
							<td class="py-2.5 px-3 text-center">
								<span class="mr-1">{r.buffer_icon}</span>
								<span style="color: #383832;">{r.buffer_days !== null ? r.buffer_days : '—'}</span>
							</td>
							<td class="py-2.5 px-3 text-center">
								<span class="mr-1">{r.diesel_pct_icon}</span>
								<span style="color: #383832;">{r.diesel_pct !== null ? r.diesel_pct + '%' : '—'}</span>
							</td>
							<td class="py-2.5 px-3 text-center" style="color: #383832;">{fmt(r.avg_fuel)}</td>
							<td class="py-2.5 px-3 text-center" style="color: #383832;">{r.avg_gen_hr ?? '—'}</td>
							<td class="py-2.5 px-2 text-center font-bold" style="color: {r.critical > 0 ? '#be2d06' : '#65655e'};">{r.critical}</td>
							<td class="py-2.5 px-2 text-center font-bold" style="color: {r.warning > 0 ? '#ff9d00' : '#65655e'};">{r.warning}</td>
							<td class="py-2.5 px-2 text-center font-bold" style="color: {r.safe > 0 ? '#007518' : '#65655e'};">{r.safe}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<!-- Legend -->
		<div class="px-4 py-2 flex gap-4 text-[10px]" style="background: #ebe8dd; border-top: 1px solid #383832; color: #65655e;">
			<span>🟢 Good</span> <span>🟡 Watch</span> <span>🟠 Warning</span> <span>🔴 Danger</span> <span>⚪ No data</span>
		</div>
	</div>
{/if}
