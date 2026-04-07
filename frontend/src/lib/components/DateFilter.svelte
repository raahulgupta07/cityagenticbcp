<script lang="ts">
	let { dateFrom = $bindable(''), dateTo = $bindable(''), siteType = $bindable('All'), onchange }: {
		dateFrom: string; dateTo: string; siteType: string; onchange?: () => void;
	} = $props();

	let expanded = $state(false);

	const quickFilters = [
		{ label: 'Yesterday', days: 1 },
		{ label: '3D', days: 3 },
		{ label: '7D', days: 7 },
		{ label: '14D', days: 14 },
		{ label: '30D', days: 30 },
		{ label: '60D', days: 60 }
	];

	function setQuick(days: number) {
		const to = new Date();
		const from = new Date();
		from.setDate(to.getDate() - days + 1);
		dateFrom = from.toISOString().slice(0, 10);
		dateTo = to.toISOString().slice(0, 10);
		onchange?.();
	}

	function activeLabel(): string {
		if (!dateFrom && !dateTo) return 'All Time';
		if (dateFrom && dateTo) return `${dateFrom} → ${dateTo}`;
		return 'Custom';
	}
</script>

<div class="flex flex-wrap items-center gap-3 mb-6">
	<!-- Quick filter buttons -->
	{#each quickFilters as qf}
		<button onclick={() => setQuick(qf.days)}
			class="px-4 py-2 text-xs font-medium rounded-lg bg-[#222a3d] text-[#dae2fd] hover:bg-[#2d3449] transition-all"
			style="border: 1px solid rgba(69,71,76,0.2)">
			{qf.label}
		</button>
	{/each}
	<button onclick={() => { dateFrom = ''; dateTo = ''; onchange?.(); }}
		class="px-4 py-2 text-xs font-medium rounded-lg bg-[#222a3d] text-[#dae2fd] hover:bg-[#2d3449] transition-all"
		style="border: 1px solid rgba(69,71,76,0.2)">
		All
	</button>

	<!-- Custom date toggle -->
	<button onclick={() => expanded = !expanded}
		class="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#222a3d] text-sm font-medium text-[#dae2fd] hover:bg-[#2d3449] transition-all ml-2"
		style="border: 1px solid rgba(69,71,76,0.2)">
		<span class="material-symbols-outlined text-sm text-[#adc6ff]">calendar_today</span>
		{activeLabel()}
		<span class="material-symbols-outlined text-xs text-[#c5c6cd] transition-transform {expanded ? 'rotate-180' : ''}">expand_more</span>
	</button>

	<!-- Site type -->
	<select bind:value={siteType} onchange={() => onchange?.()}
		class="px-4 py-2 rounded-lg bg-[#2d3449] text-sm text-[#dae2fd] focus:ring-2 focus:ring-[#adc6ff]/40 ml-auto"
		style="border: none">
		<option>All</option>
		<option>Regular</option>
		<option>LNG</option>
	</select>
</div>

<!-- Expanded date inputs -->
{#if expanded}
	<div class="flex items-center gap-3 mb-4 pl-2 animate-in">
		<span class="text-xs text-[#888fa7] uppercase tracking-widest font-semibold">From</span>
		<input type="date" bind:value={dateFrom} onchange={() => onchange?.()}
			class="bg-[#2d3449] rounded-xl px-4 py-2.5 text-sm text-[#dae2fd] focus:ring-2 focus:ring-[#adc6ff]/40" style="border:none" />
		<span class="text-xs text-[#888fa7] uppercase tracking-widest font-semibold">To</span>
		<input type="date" bind:value={dateTo} onchange={() => onchange?.()}
			class="bg-[#2d3449] rounded-xl px-4 py-2.5 text-sm text-[#dae2fd] focus:ring-2 focus:ring-[#adc6ff]/40" style="border:none" />
	</div>
{/if}
