<script lang="ts">
	import { api, downloadExcel } from '$lib/api';
	import { onMount } from 'svelte';

	let { sector = '', company = 'All' }: { sector?: string; company?: string } = $props();

	let modes: any[] = $state([]);
	let queue: any[] = $state([]);
	let generators: any[] = $state([]);
	let transfers: any[] = $state([]);
	let loadOpt: any[] = $state([]);
	let anomalies: any[] = $state([]);
	let loading = $state(true);
	let error = $state('');

	const modeSeverity: Record<string, number> = { CLOSE: 0, REDUCE: 1, MONITOR: 2, FULL: 3 };
	const modeColors: Record<string, string> = {
		FULL: '#007518',
		MONITOR: '#ff9d00',
		REDUCE: '#f95630',
		CLOSE: '#be2d06'
	};
	const urgencyColors: Record<string, string> = {
		HIGH: '#be2d06',
		MEDIUM: '#ff9d00',
		MED: '#ff9d00',
		LOW: '#007518'
	};

	let sortedModes = $derived(
		[...modes].sort(
			(a, b) => (modeSeverity[a.mode] ?? 99) - (modeSeverity[b.mode] ?? 99)
		)
	);

	let sortedQueue = $derived(
		[...queue].sort((a, b) => (a.days_left ?? a.days_of_buffer ?? 999) - (b.days_left ?? b.days_of_buffer ?? 999))
	);

	let urgentCount = $derived(
		queue.filter((q) => (q.urgency || '').toUpperCase() === 'HIGH').length
	);

	const riskSeverity: Record<string, number> = { HIGH: 0, MEDIUM: 1, LOW: 2 };

	let sortedGenerators = $derived(
		[...generators].sort(
			(a, b) =>
				(riskSeverity[(a.risk_level || '').toUpperCase()] ?? 99) -
				(riskSeverity[(b.risk_level || '').toUpperCase()] ?? 99)
		)
	);

	let highRiskCount = $derived(
		generators.filter((g) => (g.risk_level || '').toUpperCase() === 'HIGH').length
	);

	let anomalyCount = $derived(anomalies.length);

	let highAnomalies = $derived(
		anomalies.filter((a) => (a.pct_above ?? 0) > 30)
	);

	async function load() {
		loading = true;
		error = '';
		const s = sector ? `?sector=${sector}` : '';
		try {
			const [m, d] = await Promise.all([
				api.get(`/operating-modes${s}`).catch(() => []),
				api.get(`/delivery-queue${s}`).catch(() => []),
			]);
			modes = Array.isArray(m) ? m : m.modes || [];
			queue = Array.isArray(d) ? d : d.queue || [];
		} catch (e) {
			console.error(e);
			error = 'Failed to load operations data. Check your connection and try again.';
		}
		try {
			const [g, t, a] = await Promise.all([
				api.get(`/generator-risk`).catch(() => ({ generators: [] })),
				api.get(`/transfers`).catch(() => ({ transfers: [], load_optimization: [] })),
				api.get(`/anomalies`).catch(() => ({ anomalies: [] })),
			]);
			generators = g.generators || [];
			transfers = Array.isArray(t.transfers) ? t.transfers : [];
			loadOpt = t.load_optimization || [];
			anomalies = a.anomalies || [];
		} catch {}
		loading = false;
	}

	let prevSector = '';
	onMount(() => { prevSector = sector; load(); });
	$effect(() => {
		if (sector !== prevSector) {
			prevSector = sector;
			load();
		}
	});

	let search = $state('');
	const matchSearch = (r: any) => Object.values(r).some(v => String(v).toLowerCase().includes(search.toLowerCase()));
	const filteredModes = $derived(search ? sortedModes.filter(matchSearch) : sortedModes);
	const filteredQueue = $derived(search ? sortedQueue.filter(matchSearch) : sortedQueue);
	const filteredGenerators = $derived(search ? sortedGenerators.filter(matchSearch) : sortedGenerators);
	const filteredTransfers = $derived(search ? transfers.filter(matchSearch) : transfers);
	const filteredLoadOpt = $derived(search ? loadOpt.filter(matchSearch) : loadOpt);
	const filteredAnomalies = $derived(search ? anomalies.filter(matchSearch) : anomalies);

	// Pagination for Operating Modes table
	let modesPage = $state(1);
	const modesPageSize = 15;
	const modesTotalPages = $derived(Math.ceil(filteredModes.length / modesPageSize));
	const paginatedModes = $derived(filteredModes.slice((modesPage - 1) * modesPageSize, modesPage * modesPageSize));

	// Pagination for Delivery Queue table
	let queuePage = $state(1);
	const queuePageSize = 15;
	const queueTotalPages = $derived(Math.ceil(filteredQueue.length / queuePageSize));
	const paginatedQueue = $derived(filteredQueue.slice((queuePage - 1) * queuePageSize, queuePage * queuePageSize));

	// Reset pages when search changes
	$effect(() => { search; modesPage = 1; queuePage = 1; });

	function fmt(v: any): string {
		if (v == null) return '—';
		if (typeof v === 'number') return v.toLocaleString();
		return String(v);
	}

	function badgeStyle(color: string): string {
		return `background: ${color}; color: white; padding: 2px 10px; font-size: 0.75rem; font-weight: 800; letter-spacing: 0.05em; text-transform: uppercase;`;
	}
</script>

{#if loading}
	<div
		class="text-center py-8 font-bold uppercase"
		style="background: #feffd6; color: #65655e; border: 2px solid #383832;"
	>
		Loading operations data...
	</div>
{:else if error}
	<div class="text-center py-16" style="background: #f6f4e9; border: 2px solid #383832;">
		<span class="material-symbols-outlined text-4xl" style="color: #be2d06;">error</span>
		<p class="font-bold mt-3 uppercase tracking-widest text-sm" style="color: #be2d06;">{error}</p>
		<button onclick={load} class="mt-4 px-6 py-2 text-xs font-black uppercase"
			style="background: #383832; color: #feffd6; border: 2px solid #383832;">
			<span class="material-symbols-outlined text-sm align-middle">refresh</span> RETRY
		</button>
	</div>
{:else}
	<div class="px-3 py-2 flex items-center gap-2" style="background: #ebe8dd; border-bottom: 1px solid #383832; margin-bottom: 1rem; border: 2px solid #383832;">
		<span class="material-symbols-outlined text-sm" style="color: #65655e;">search</span>
		<input type="text" bind:value={search} placeholder="QUICK_SEARCH..."
			class="flex-1 px-2 py-1 text-xs font-mono uppercase"
			style="background: white; border: 1px solid #383832; color: #383832;" />
	</div>

	<!-- SECTION 1: Operating Modes -->
	<div style="background: #feffd6; border: 2px solid #383832; margin-bottom: 1.5rem;">
		<!-- Header -->
		<div
			class="px-4 py-2 font-black uppercase tracking-wider text-sm flex items-center justify-between"
			style="background: #383832; color: #feffd6;"
		>
			<span>OPERATING_MODES</span>
			<div class="flex items-center gap-3">
				<button onclick={() => downloadExcel(sortedModes, 'Operating Modes', { statusColumns: ['operating_mode'] })}
					class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
					style="color: #00fc40;">
					<span class="material-symbols-outlined text-sm">download</span> EXCEL
				</button>
				<button onclick={() => downloadExcel(sortedModes, 'Operating Modes', { statusColumns: ['operating_mode'] })}
					class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-60 hover:opacity-100"
					style="color: #feffd6;">
					<span class="material-symbols-outlined text-sm">download</span> CSV
				</button>
				<span
					class="text-xs font-bold px-2 py-0.5"
					style="background: #feffd6; color: #383832;"
				>
					{sortedModes.length} SITES
				</span>
			</div>
		</div>

		{#if sortedModes.length === 0}
			<div class="p-4 text-center text-sm" style="color: #65655e;">
				No operating mode data available.
			</div>
		{:else}
			<div style="overflow-x: auto;">
				<table style="width: 100%; border-collapse: collapse; font-size: 0.8rem;">
					<thead>
						<tr style="background: #ebe8dd;">
							<th
								class="font-black uppercase text-left px-3 py-2"
								style="border-bottom: 2px solid #383832; color: #383832;">SITE_ID</th
							>
							<th
								class="font-black uppercase text-left px-3 py-2"
								style="border-bottom: 2px solid #383832; color: #383832;">SITE_CODE</th
							>
							<th
								class="font-black uppercase text-left px-3 py-2"
								style="border-bottom: 2px solid #383832; color: #383832;">SEGMENT</th
							>
							<th
								class="font-black uppercase text-left px-3 py-2"
								style="border-bottom: 2px solid #383832; color: #383832;">SECTOR</th
							>
							<th
								class="font-black uppercase text-center px-3 py-2"
								style="border-bottom: 2px solid #383832; color: #383832;">MODE</th
							>
							<th
								class="font-black uppercase text-right px-3 py-2"
								style="border-bottom: 2px solid #383832; color: #383832;">BUFFER_DAYS</th
							>
							<th
								class="font-black uppercase text-right px-3 py-2"
								style="border-bottom: 2px solid #383832; color: #383832;">DAILY_COST</th
							>
							<th
								class="font-black uppercase text-right px-3 py-2"
								style="border-bottom: 2px solid #383832; color: #383832;">ENERGY_%</th
							>
							<th
								class="font-black uppercase text-left px-3 py-2"
								style="border-bottom: 2px solid #383832; color: #383832;">ACTION</th
							>
						</tr>
					</thead>
					<tbody>
						{#each paginatedModes as row, i}
							{@const rowIdx = (modesPage - 1) * modesPageSize + i}
							<tr style="background: {rowIdx % 2 === 0 ? 'white' : '#f6f4e9'};">
								<td
									class="px-3 py-2 font-bold"
									style="border-bottom: 1px solid #ebe8dd; color: #383832;"
								>
									{row.site_id || '—'}
								</td>
								<td
									class="px-3 py-2 font-mono text-xs"
									style="border-bottom: 1px solid #ebe8dd; color: #383832;"
								>
									{row.site_code || row.region || ''}
								</td>
								<td
									class="px-3 py-2 text-xs"
									style="border-bottom: 1px solid #ebe8dd; color: #383832;"
								>
									{row.segment_name || ''}
								</td>
								<td
									class="px-3 py-2"
									style="border-bottom: 1px solid #ebe8dd; color: #383832;"
								>
									{row.sector_id || row.sector || '—'}
								</td>
								<td
									class="px-3 py-2 text-center"
									style="border-bottom: 1px solid #ebe8dd;"
								>
									<span style={badgeStyle(modeColors[row.mode] || '#383832')}>
										{row.mode || '—'}
									</span>
								</td>
								<td
									class="px-3 py-2 text-right font-mono"
									style="border-bottom: 1px solid #ebe8dd; color: #383832;"
								>
									{fmt(row.days_of_buffer ?? row.buffer_days)}
								</td>
								<td
									class="px-3 py-2 text-right font-mono"
									style="border-bottom: 1px solid #ebe8dd; color: #383832;"
								>
									{fmt(row.daily_cost)}
								</td>
								<td
									class="px-3 py-2 text-right font-mono"
									style="border-bottom: 1px solid #ebe8dd; color: #383832;"
								>
									{row.energy_pct != null ? `${row.energy_pct.toFixed(1)}%` : '—'}
								</td>
								<td
									class="px-3 py-2 text-sm"
									style="border-bottom: 1px solid #ebe8dd; color: #383832;"
								>
									{row.reason || row.action || '—'}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			{#if modesTotalPages > 1}
				<div class="px-4 py-2 flex items-center justify-between" style="background: white; border-top: 1px solid #383832;">
					<span class="text-[10px] font-mono" style="color: #65655e;">
						Page {modesPage} of {modesTotalPages} ({filteredModes.length} sites)
					</span>
					<div class="flex gap-1">
						<button onclick={() => modesPage = Math.max(1, modesPage - 1)}
							disabled={modesPage <= 1}
							class="px-2 py-1 text-[10px] font-black uppercase"
							style="background: {modesPage <= 1 ? '#ebe8dd' : '#383832'}; color: {modesPage <= 1 ? '#65655e' : '#feffd6'}; border: 1px solid #383832;">
							PREV
						</button>
						{#each Array(modesTotalPages) as _, p}
							<button onclick={() => modesPage = p + 1}
								class="px-2 py-1 text-[10px] font-black"
								style="background: {modesPage === p + 1 ? '#383832' : 'white'}; color: {modesPage === p + 1 ? '#feffd6' : '#383832'}; border: 1px solid #383832;">
								{p + 1}
							</button>
						{/each}
						<button onclick={() => modesPage = Math.min(modesTotalPages, modesPage + 1)}
							disabled={modesPage >= modesTotalPages}
							class="px-2 py-1 text-[10px] font-black uppercase"
							style="background: {modesPage >= modesTotalPages ? '#ebe8dd' : '#383832'}; color: {modesPage >= modesTotalPages ? '#65655e' : '#feffd6'}; border: 1px solid #383832;">
							NEXT
						</button>
					</div>
				</div>
			{/if}
		{/if}
	</div>

	<!-- SECTION 2: Delivery Queue -->
	<div style="background: #feffd6; border: 2px solid #383832;">
		<!-- Header -->
		<div
			class="px-4 py-2 font-black uppercase tracking-wider text-sm flex items-center justify-between"
			style="background: #383832; color: #feffd6;"
		>
			<span>DELIVERY_QUEUE</span>
			<div class="flex items-center gap-3">
				<button onclick={() => downloadExcel(sortedQueue, 'Delivery Queue', { statusColumns: ['urgency'] })}
					class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
					style="color: #00fc40;">
					<span class="material-symbols-outlined text-sm">download</span> EXCEL
				</button>
				<button onclick={() => downloadExcel(sortedQueue, 'Delivery Queue', { statusColumns: ['urgency'] })}
					class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-60 hover:opacity-100"
					style="color: #feffd6;">
					<span class="material-symbols-outlined text-sm">download</span> CSV
				</button>
				<span
					class="text-xs font-bold px-2 py-0.5"
					style="background: {urgentCount > 0 ? '#be2d06' : '#feffd6'}; color: {urgentCount > 0
						? 'white'
						: '#383832'};"
				>
					{urgentCount} URGENT
				</span>
			</div>
		</div>

		{#if sortedQueue.length === 0}
			<div class="p-4 text-center text-sm" style="color: #65655e;">
				No deliveries pending.
			</div>
		{:else}
			<div style="overflow-x: auto;">
				<table style="width: 100%; border-collapse: collapse; font-size: 0.8rem;">
					<thead>
						<tr style="background: #ebe8dd;">
							<th
								class="font-black uppercase text-left px-3 py-2"
								style="border-bottom: 2px solid #383832; color: #383832;">SITE_ID</th
							>
							<th
								class="font-black uppercase text-left px-3 py-2"
								style="border-bottom: 2px solid #383832; color: #383832;">SITE_CODE</th
							>
							<th
								class="font-black uppercase text-left px-3 py-2"
								style="border-bottom: 2px solid #383832; color: #383832;">SECTOR</th
							>
							<th
								class="font-black uppercase text-center px-3 py-2"
								style="border-bottom: 2px solid #383832; color: #383832;">URGENCY</th
							>
							<th
								class="font-black uppercase text-right px-3 py-2"
								style="border-bottom: 2px solid #383832; color: #383832;">DAYS_LEFT</th
							>
							<th
								class="font-black uppercase text-right px-3 py-2"
								style="border-bottom: 2px solid #383832; color: #383832;">TANK_L</th
							>
							<th
								class="font-black uppercase text-right px-3 py-2"
								style="border-bottom: 2px solid #383832; color: #383832;">NEED_L</th
							>
							<th
								class="font-black uppercase text-left px-3 py-2"
								style="border-bottom: 2px solid #383832; color: #383832;">DELIVER_BY</th
							>
							<th
								class="font-black uppercase text-right px-3 py-2"
								style="border-bottom: 2px solid #383832; color: #383832;">EST_COST</th
							>
						</tr>
					</thead>
					<tbody>
						{#each paginatedQueue as row, i}
							{@const rowIdx = (queuePage - 1) * queuePageSize + i}
							{@const urg = (row.urgency || '').toUpperCase()}
							<tr style="background: {rowIdx % 2 === 0 ? 'white' : '#f6f4e9'};">
								<td
									class="px-3 py-2 font-bold"
									style="border-bottom: 1px solid #ebe8dd; color: #383832;"
								>
									{row.site_id || '—'}
								</td>
								<td
									class="px-3 py-2 font-mono text-xs"
									style="border-bottom: 1px solid #ebe8dd; color: #383832;"
								>
									{row.site_code || row.region || ''}
								</td>
								<td
									class="px-3 py-2"
									style="border-bottom: 1px solid #ebe8dd; color: #383832;"
								>
									{row.sector_id || row.sector || '—'}
								</td>
								<td
									class="px-3 py-2 text-center"
									style="border-bottom: 1px solid #ebe8dd;"
								>
									<span style={badgeStyle(urgencyColors[urg] || '#383832')}>
										{urg || '—'}
									</span>
								</td>
								<td
									class="px-3 py-2 text-right font-mono"
									style="border-bottom: 1px solid #ebe8dd; color: {(row.days_left ??
										row.days_of_buffer ??
										999) <= 2
										? '#be2d06'
										: '#383832'}; font-weight: {(row.days_left ??
										row.days_of_buffer ??
										999) <= 2
										? '800'
										: '400'};"
								>
									{fmt(row.days_left ?? row.days_of_buffer)}
								</td>
								<td
									class="px-3 py-2 text-right font-mono"
									style="border-bottom: 1px solid #ebe8dd; color: #383832;"
								>
									{fmt(row.tank_balance ?? row.tank_l)}
								</td>
								<td
									class="px-3 py-2 text-right font-mono"
									style="border-bottom: 1px solid #ebe8dd; color: #383832;"
								>
									{fmt(row.liters_needed ?? row.need_l)}
								</td>
								<td
									class="px-3 py-2"
									style="border-bottom: 1px solid #ebe8dd; color: #383832;"
								>
									{row.delivery_by ?? row.deliver_by ?? '—'}
								</td>
								<td
									class="px-3 py-2 text-right font-mono"
									style="border-bottom: 1px solid #ebe8dd; color: #383832;"
								>
									{fmt(row.est_cost)}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			{#if queueTotalPages > 1}
				<div class="px-4 py-2 flex items-center justify-between" style="background: white; border-top: 1px solid #383832;">
					<span class="text-[10px] font-mono" style="color: #65655e;">
						Page {queuePage} of {queueTotalPages} ({filteredQueue.length} sites)
					</span>
					<div class="flex gap-1">
						<button onclick={() => queuePage = Math.max(1, queuePage - 1)}
							disabled={queuePage <= 1}
							class="px-2 py-1 text-[10px] font-black uppercase"
							style="background: {queuePage <= 1 ? '#ebe8dd' : '#383832'}; color: {queuePage <= 1 ? '#65655e' : '#feffd6'}; border: 1px solid #383832;">
							PREV
						</button>
						{#each Array(queueTotalPages) as _, p}
							<button onclick={() => queuePage = p + 1}
								class="px-2 py-1 text-[10px] font-black"
								style="background: {queuePage === p + 1 ? '#383832' : 'white'}; color: {queuePage === p + 1 ? '#feffd6' : '#383832'}; border: 1px solid #383832;">
								{p + 1}
							</button>
						{/each}
						<button onclick={() => queuePage = Math.min(queueTotalPages, queuePage + 1)}
							disabled={queuePage >= queueTotalPages}
							class="px-2 py-1 text-[10px] font-black uppercase"
							style="background: {queuePage >= queueTotalPages ? '#ebe8dd' : '#383832'}; color: {queuePage >= queueTotalPages ? '#65655e' : '#feffd6'}; border: 1px solid #383832;">
							NEXT
						</button>
					</div>
				</div>
			{/if}
		{/if}
	</div>

	<!-- SECTION 3: At-Risk Generators -->
	<div style="background: #feffd6; border: 2px solid #383832; margin-top: 1.5rem;">
		<div
			class="px-4 py-2 font-black uppercase tracking-wider text-sm flex items-center justify-between"
			style="background: #383832; color: #feffd6;"
		>
			<span>MAINTENANCE_RISK</span>
			<div class="flex items-center gap-3">
				<button onclick={() => downloadExcel(sortedGenerators, 'Generator Risk')}
					class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
					style="color: #00fc40;">
					<span class="material-symbols-outlined text-sm">download</span> EXCEL
				</button>
				<span
					class="text-xs font-bold px-2 py-0.5"
					style="background: {highRiskCount > 0 ? '#be2d06' : '#feffd6'}; color: {highRiskCount > 0 ? 'white' : '#383832'};"
				>
					{highRiskCount} HIGH
				</span>
			</div>
		</div>

		{#if sortedGenerators.length === 0}
			<div class="p-4 text-center text-sm" style="color: #65655e;">
				No generator risk data available.
			</div>
		{:else}
			<div style="overflow-x: auto;">
				<table style="width: 100%; border-collapse: collapse; font-size: 0.8rem;">
					<thead>
						<tr style="background: #ebe8dd;">
							<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">SITE_ID</th>
							<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">MODEL</th>
							<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">TOTAL_HOURS</th>
							<th class="font-black uppercase text-center px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">RISK_LEVEL</th>
							<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">HOURS_UNTIL_SERVICE</th>
							<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">NOTE</th>
						</tr>
					</thead>
					<tbody>
						{#each filteredGenerators as row, i}
							{@const risk = (row.risk_level || '').toUpperCase()}
							<tr style="background: {i % 2 === 0 ? 'white' : '#f6f4e9'};">
								<td class="px-3 py-2 font-bold" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.site_id || '—'}</td>
								<td class="px-3 py-2" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.model || '—'}</td>
								<td class="px-3 py-2 text-right font-mono" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{fmt(row.total_hours)}</td>
								<td class="px-3 py-2 text-center" style="border-bottom: 1px solid #ebe8dd;">
									<span style={badgeStyle(urgencyColors[risk] || '#383832')}>{risk || '—'}</span>
								</td>
								<td class="px-3 py-2 text-right font-mono" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{fmt(row.hours_until_service)}</td>
								<td class="px-3 py-2 text-sm" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.note || '—'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>

	<!-- SECTION 4: Recommended Transfers -->
	<div style="background: #feffd6; border: 2px solid #383832; margin-top: 1.5rem;">
		<div
			class="px-4 py-2 font-black uppercase tracking-wider text-sm flex items-center justify-between"
			style="background: #383832; color: #feffd6;"
		>
			<span>FUEL_TRANSFERS</span>
			<div class="flex items-center gap-3">
				<button onclick={() => downloadExcel(transfers, 'Fuel Transfers')}
					class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
					style="color: #00fc40;">
					<span class="material-symbols-outlined text-sm">download</span> EXCEL
				</button>
				<span
					class="text-xs font-bold px-2 py-0.5"
					style="background: #feffd6; color: #383832;"
				>
					{transfers.length} TRANSFERS
				</span>
			</div>
		</div>

		{#if transfers.length === 0}
			<div class="p-4 text-center text-sm font-bold uppercase" style="color: #007518;">
				NO_TRANSFERS_NEEDED
			</div>
		{:else}
			<div style="overflow-x: auto;">
				<table style="width: 100%; border-collapse: collapse; font-size: 0.8rem;">
					<thead>
						<tr style="background: #ebe8dd;">
							<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">FROM_SITE</th>
							<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">TO_SITE</th>
							<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">TRANSFER_L</th>
							<th class="font-black uppercase text-center px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">SAVES_DELIVERY</th>
						</tr>
					</thead>
					<tbody>
						{#each filteredTransfers as row, i}
							{@const saves = row.saves_delivery ? 'YES' : 'NO'}
							<tr style="background: {i % 2 === 0 ? 'white' : '#f6f4e9'};">
								<td class="px-3 py-2 font-bold" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.from_site || '—'}</td>
								<td class="px-3 py-2 font-bold" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.to_site || '—'}</td>
								<td class="px-3 py-2 text-right font-mono" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{fmt(row.transfer_l)}</td>
								<td class="px-3 py-2 text-center" style="border-bottom: 1px solid #ebe8dd;">
									<span style={badgeStyle(saves === 'YES' ? '#007518' : '#ff9d00')}>{saves}</span>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>

	<!-- SECTION 5: Load Optimization -->
	<div style="background: #feffd6; border: 2px solid #383832; margin-top: 1.5rem;">
		<div
			class="px-4 py-2 font-black uppercase tracking-wider text-sm flex items-center justify-between"
			style="background: #383832; color: #feffd6;"
		>
			<span>LOAD_OPTIMIZATION</span>
			<div class="flex items-center gap-3">
				<button onclick={() => downloadExcel(loadOpt, 'Load Optimization')}
					class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
					style="color: #00fc40;">
					<span class="material-symbols-outlined text-sm">download</span> EXCEL
				</button>
				<span
					class="text-xs font-bold px-2 py-0.5"
					style="background: #feffd6; color: #383832;"
				>
					{loadOpt.length} SITES
				</span>
			</div>
		</div>

		{#if loadOpt.length === 0}
			<div class="p-4 text-center text-sm" style="color: #65655e;">
				No load optimization data available.
			</div>
		{:else}
			<div style="overflow-x: auto;">
				<table style="width: 100%; border-collapse: collapse; font-size: 0.8rem;">
					<thead>
						<tr style="background: #ebe8dd;">
							<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">SITE_ID</th>
							<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">MODEL</th>
							<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">KVA/L</th>
							<th class="font-black uppercase text-center px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">RANK</th>
							<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">RECOMMENDATION</th>
							<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">SAVINGS_L/HR</th>
						</tr>
					</thead>
					<tbody>
						{#each filteredLoadOpt as row, i}
							<tr style="background: {i % 2 === 0 ? 'white' : '#f6f4e9'};">
								<td class="px-3 py-2 font-bold" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.site_id || '—'}</td>
								<td class="px-3 py-2" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.model || '—'}</td>
								<td class="px-3 py-2 text-right font-mono" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.kva_per_l != null ? row.kva_per_l.toFixed(2) : '—'}</td>
								<td class="px-3 py-2 text-center font-mono" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{fmt(row.rank)}</td>
								<td class="px-3 py-2 text-sm" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.recommendation || '—'}</td>
								<td class="px-3 py-2 text-right font-mono" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.savings_l_hr != null ? row.savings_l_hr.toFixed(2) : '—'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>

	<!-- SECTION 6: Consumption Anomalies -->
	<div style="background: #feffd6; border: 2px solid #383832; margin-top: 1.5rem;">
		<div
			class="px-4 py-2 font-black uppercase tracking-wider text-sm flex items-center justify-between"
			style="background: #383832; color: #feffd6;"
		>
			<span>ANOMALY_DETECTION</span>
			<div class="flex items-center gap-3">
				<button onclick={() => downloadExcel(anomalies, 'Anomaly Detection')}
					class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
					style="color: #00fc40;">
					<span class="material-symbols-outlined text-sm">download</span> EXCEL
				</button>
				<span
					class="text-xs font-bold px-2 py-0.5"
					style="background: {anomalyCount > 0 ? '#be2d06' : '#feffd6'}; color: {anomalyCount > 0 ? 'white' : '#383832'};"
				>
					{anomalyCount} ANOMALIES
				</span>
			</div>
		</div>

		{#if anomalies.length === 0}
			<div class="p-4 text-center text-sm" style="color: #65655e;">
				No consumption anomalies detected.
			</div>
		{:else}
			<div style="overflow-x: auto;">
				<table style="width: 100%; border-collapse: collapse; font-size: 0.8rem;">
					<thead>
						<tr style="background: #ebe8dd;">
							<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">SITE_ID</th>
							<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">DAILY_USED</th>
							<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">7D_AVG</th>
							<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">PCT_ABOVE</th>
							<th class="font-black uppercase text-right px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">EXCESS_L</th>
							<th class="font-black uppercase text-left px-3 py-2" style="border-bottom: 2px solid #383832; color: #383832;">POSSIBLE_CAUSE</th>
						</tr>
					</thead>
					<tbody>
						{#each filteredAnomalies as row, i}
							{@const pctAbove = row.pct_above ?? 0}
							{@const isHigh = pctAbove > 30}
							<tr style="background: {isHigh ? '#fff0f0' : (i % 2 === 0 ? 'white' : '#f6f4e9')};">
								<td class="px-3 py-2 font-bold" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.site_id || '—'}</td>
								<td class="px-3 py-2 text-right font-mono" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{fmt(row.daily_used)}</td>
								<td class="px-3 py-2 text-right font-mono" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{fmt(row.avg_7d)}</td>
								<td class="px-3 py-2 text-right font-mono font-bold" style="border-bottom: 1px solid #ebe8dd; color: {isHigh ? '#be2d06' : '#383832'};">
									{pctAbove.toFixed(1)}%
								</td>
								<td class="px-3 py-2 text-right font-mono" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{fmt(row.excess_l)}</td>
								<td class="px-3 py-2 text-sm" style="border-bottom: 1px solid #ebe8dd; color: #383832;">{row.possible_cause || '—'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>
{/if}
