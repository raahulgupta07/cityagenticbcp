<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import SmartTable from '$lib/components/SmartTable.svelte';

	let { sector = '' }: { sector?: string } = $props();

	let loading = $state(true);
	let modes: any[] = $state([]);
	let queue: any[] = $state([]);
	let scores: any[] = $state([]);
	let alerts: any[] = $state([]);

	async function load() {
		loading = true;
		try {
			const s = sector ? `?sector=${sector}` : '';
			[modes, queue, scores, alerts] = await Promise.all([
				api.get(`/operating-modes${s}`),
				api.get(`/delivery-queue${s}`),
				api.get('/bcp-scores'),
				api.get('/alerts'),
			]);
		} catch (e) { console.error(e); }
		loading = false;
	}

	onMount(load);
	$effect(() => { sector; load(); });
</script>

{#if loading}
	<p class="text-sm py-4 text-center" style="color: #65655e;">Loading operations data...</p>
{:else}
	<!-- Operating Modes -->
	{#if modes.length > 0}
		<h2 class="text-lg font-black uppercase mt-6 mb-3" style="color: #383832;">🎯 Operating Modes</h2>
		<SmartTable data={modes} columns={[
			{ key: 'site_id', label: 'Site' }, { key: 'sector_id', label: 'Sector' },
			{ key: 'mode', label: 'Mode' }, { key: 'days_of_buffer', label: 'Buffer Days' },
			{ key: 'reason', label: 'Action' }
		]} title="Operating Mode Recommendations" />
	{/if}

	<!-- Delivery Queue -->
	{#if queue.length > 0}
		<h2 class="text-lg font-black uppercase mt-6 mb-3" style="color: #383832;">🚛 Fuel Delivery Queue</h2>
		<div class="grid grid-cols-3 gap-3 mb-3">
			<div class="p-3 text-center" style="background: white; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
				<div class="text-2xl font-bold" style="color: #383832;">{queue.length}</div>
				<div class="text-xs" style="color: #65655e;">Sites Need Fuel</div>
			</div>
			<div class="p-3 text-center" style="background: white; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
				<div class="text-2xl font-bold" style="color: #383832;">{Math.round(queue.reduce((s: number, r: any) => s + (r.liters_needed || 0), 0)).toLocaleString()} L</div>
				<div class="text-xs" style="color: #65655e;">Total Needed</div>
			</div>
			<div class="p-3 text-center" style="background: white; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
				<div class="text-2xl font-bold" style="color: #383832;">{Math.round(queue.reduce((s: number, r: any) => s + (r.est_cost || 0), 0)).toLocaleString()}</div>
				<div class="text-xs" style="color: #65655e;">Est. Cost (MMK)</div>
			</div>
		</div>
		<SmartTable data={queue} columns={[
			{ key: 'site_id', label: 'Site' }, { key: 'urgency', label: 'Urgency' },
			{ key: 'days_of_buffer', label: 'Days Left' }, { key: 'liters_needed', label: 'Need (L)' },
			{ key: 'delivery_by', label: 'Deliver By' }, { key: 'est_cost', label: 'Cost (MMK)' }
		]} title="Delivery Queue" />
	{/if}

	<!-- BCP Scores -->
	{#if scores.length > 0}
		<h2 class="text-lg font-black uppercase mt-6 mb-3" style="color: #383832;">🛡️ BCP Risk Scores</h2>
		{@const grades = ['A','B','C','D','F']}
		{@const gradeColors: Record<string, string> = { A: 'background: #007518; color: white;', B: 'background: #006f7c; color: white;', C: 'background: #ff9d00; color: #383832;', D: 'background: #9d4867; color: white;', F: 'background: #be2d06; color: white;' }}
		<div class="flex gap-2 mb-3">
			{#each grades as g}
				{@const cnt = scores.filter((s: any) => s.grade === g).length}
				<div class="px-4 py-2 text-center font-bold" style="{gradeColors[g]}">{g}: {cnt}</div>
			{/each}
		</div>
		<SmartTable data={scores.sort((a: any, b: any) => (a.bcp_score || 0) - (b.bcp_score || 0))} columns={[
			{ key: 'site_id', label: 'Site' }, { key: 'sector_id', label: 'Sector' },
			{ key: 'bcp_score', label: 'Score' }, { key: 'grade', label: 'Grade' }
		]} title="BCP Scores (worst first)" />
	{/if}

	<!-- Alerts -->
	{#if alerts.length > 0}
		<h2 class="text-lg font-black uppercase mt-6 mb-3" style="color: #383832;">🔔 Active Alerts</h2>
		<SmartTable data={alerts} columns={[
			{ key: 'site_id', label: 'Site' }, { key: 'alert_type', label: 'Type' },
			{ key: 'severity', label: 'Severity' }, { key: 'message', label: 'Message' }
		]} title={`${alerts.length} Active Alerts`} />
	{/if}
{/if}
