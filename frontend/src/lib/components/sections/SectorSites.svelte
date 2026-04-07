<script lang="ts">
	import { api, downloadExcel } from '$lib/api';
	import { onMount } from 'svelte';

	let { sector = '', company = 'All', sites: selectedSiteIds = [] as string[] }: { sector?: string; company?: string; sites?: string[] } = $props();
	let sites: any[] = $state([]);
	let count = $state(0);
	let loading = $state(true);

	async function load() {
		loading = true;
		try {
			const p = sector ? `?sector=${sector}` : '';
			const data = await api.get(`/sector-sites${p}`);
			sites = (data.sites || []).sort((a: any, b: any) => (b.exp_pct || 0) - (a.exp_pct || 0));
			count = data.count || 0;
		} catch (e) {
			console.error(e);
		}
		loading = false;
	}

	onMount(load);
	$effect(() => {
		sector;
		load();
	});

	function icon(val: number, thresholds: number[], reverse = false): string {
		const [g, y, a] = thresholds;
		if (reverse) return val <= g ? '\u{1F7E2}' : val <= y ? '\u{1F7E1}' : val <= a ? '\u{1F7E0}' : '\u{1F534}';
		return val >= g ? '\u{1F7E2}' : val >= y ? '\u{1F7E1}' : val >= a ? '\u{1F7E0}' : '\u{1F534}';
	}

	function fmt(v: number): string {
		if (!v) return '0';
		if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M';
		if (v >= 1e3) return (v / 1e3).toFixed(1) + 'K';
		return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
	}

	function fmtDec(v: number, d = 1): string {
		if (!v && v !== 0) return '0';
		return v.toFixed(d);
	}

	let search = $state('');
	const filteredSites = $derived.by(() => {
		let f = sites;
		if (company && company !== 'All') f = f.filter((r: any) => r.company === company);
		if (selectedSiteIds && selectedSiteIds.length > 0) f = f.filter((r: any) => selectedSiteIds.includes(r.site_id));
		if (search) f = f.filter(r => Object.values(r).some(v => String(v).toLowerCase().includes(search.toLowerCase())));
		return f;
	});


	const siteCols = [
		{ label: 'SITE', formula: 'cost_center_code (PK)', align: 'left' },
		{ label: 'SITE_CODE', formula: 'sector-store_code', align: 'left' },
		{ label: 'SEGMENT', formula: 'from store_master', align: 'left' },
		{ label: 'SIZE', formula: 'store_master', align: 'center' },
		{ label: 'PRICE/L', formula: 'latest fuel price', align: 'center' },
		{ label: 'BLACKOUT_HR', formula: 'last day', align: 'center' },
		{ label: 'BUFFER_DAY', formula: 'tank÷burn', align: 'center' },
		{ label: 'TANK', formula: 'last day (L)', align: 'center' },
		{ label: 'BURN/DAY', formula: 'last day (L)', align: 'center' },
		{ label: 'SALES_1D', formula: 'last day sales', align: 'center' },
		{ label: 'SALES_3D', formula: 'avg 3 days', align: 'center' },
		{ label: 'SALES_AVG', formula: 'period avg', align: 'center' },
		{ label: 'COST_1D', formula: 'last day fuel cost', align: 'center' },
		{ label: 'COST_3D', formula: 'avg 3 days', align: 'center' },
		{ label: 'COST_AVG', formula: 'period avg', align: 'center' },
		{ label: 'EXP%_1D', formula: 'cost÷sales last day', align: 'center' },
		{ label: 'EXP%_3D', formula: 'cost÷sales 3d avg', align: 'center' },
		{ label: 'EXP%_TOTAL', formula: 'total cost÷total sales', align: 'center' },
		{ label: 'MARGIN%', formula: 'margin÷sales total', align: 'center' },
		{ label: 'MARGIN%_1D', formula: 'last day', align: 'center' },
		{ label: 'MARGIN%_3D', formula: '3d avg', align: 'center' },
		{ label: 'ACTION', formula: 'by diesel% threshold', align: 'center' },
	];

	const actionColors: Record<string, string> = {
		OPEN: '#007518',
		MONITOR: '#ff9d00',
		REDUCE: '#f95630',
		CLOSE: '#be2d06'
	};
</script>

{#if loading}
	<p class="text-sm py-4 text-center" style="color: #65655e;">Loading sector sites...</p>
{:else if sites.length > 0}
	<h2 class="text-lg font-black uppercase mt-6 mb-3" style="color: #383832;">
		{sector || 'ALL'} &mdash; {count} sites
	</h2>

	<!-- Build aggregation maps for 3 levels: Group, Company, Segment -->
	{@const buildAgg = (sites: any[], keyFn: (s: any) => string, extraFn?: (s: any) => { sector?: string; company?: string }) => {
		const map = new Map<string, any>();
		for (const s of sites) {
			const key = keyFn(s) || 'Unknown';
			const e = map.get(key) || { count: 0, crit: 0, warn: 0, safe: 0, sumBuffer: 0, sumPrice: 0, sumBO: 0, boCount: 0, sumExp: 0, sumSales: 0, sumCost: 0, sumMargin: 0, sumTank: 0, sumBurn: 0, sumTotalFuel: 0, sumTotalGenHr: 0, sectors: new Set(), companies: new Set() };
			const buf = s.buffer_days || 0;
			e.count++; e.sumBuffer += buf; e.sumPrice += (s.price || 0);
			if (s.blackout_hr && s.blackout_hr > 0) { e.sumBO += s.blackout_hr; e.boCount++; }
			e.sumExp += (s.exp_pct || 0);
			e.sumSales += (s.total_sales || 0); e.sumCost += (s.daily_cost || 0); e.sumMargin += (s.margin_pct || 0);
			if (s.sector_id) e.sectors.add(s.sector_id);
			if (s.company) e.companies.add(s.company);
			e.sumTank += (s.tank || 0); e.sumBurn += (s.daily_fuel || 0);
			e.sumTotalFuel += (s.total_fuel || 0); e.sumTotalGenHr += (s.total_gen_hr || 0);
			e.crit += (buf > 0 && buf < 3 ? 1 : 0); e.warn += (buf >= 3 && buf < 7 ? 1 : 0); e.safe += (buf >= 7 ? 1 : 0);
			map.set(key, e);
		}
		return [...map.entries()].sort((a, b) => b[1].count - a[1].count);
	}}
	{@const groupAgg = buildAgg(sites, () => 'ALL')}
	{@const companyAgg = buildAgg(sites, (s: any) => s.company)}
	{@const segmentAgg = buildAgg(sites, (s: any) => s.segment_name)}
	<!-- Column definitions with formulas -->
	{@const baseCols = [
		{ key: 'name', label: 'NAME', formula: 'Group / Company / Segment' },
		{ key: 'sector', label: 'SECTOR', formula: 'sector_id' },
		{ key: 'company', label: 'COMPANY', formula: 'company' },
		{ key: 'outlets', label: 'OUTLETS', formula: 'COUNT(sites) on last day' },
		{ key: 'price', label: 'PRICE/L', formula: 'AVG(price) last day' },
		{ key: 'bo', label: 'BLACKOUT_HR', formula: 'AVG(blackout_hr) non-null days' },
		{ key: 'exp', label: 'EXP%_SALE', formula: 'AVG(cost÷sales×100) last day' },
		{ key: 'buffer', label: 'BUFFER_DAY', formula: 'SUM(tank)÷SUM(burn) last day' },
		{ key: 'sales', label: 'SALES_TOTAL', formula: 'SUM(sales_amt) all dates' },
		{ key: 'cost', label: 'DIESEL_COST', formula: 'used×price last day' },
		{ key: 'margin', label: 'MARGIN%', formula: 'AVG(margin÷sales) all dates' },
		{ key: 'tank', label: 'TANK', formula: 'SUM(tank_balance) last day' },
		{ key: 'burn', label: 'BURN/DAY', formula: 'SUM(daily_used) last day' },
		{ key: 'totalFuel', label: 'TOTAL_FUEL', formula: 'SUM(used) all days' },
		{ key: 'totalGenHr', label: 'TOTAL_GEN_HR', formula: 'SUM(gen_hr) all days' },
		{ key: 'crit', label: 'CRIT', formula: 'buffer<3d last day' },
		{ key: 'warn', label: 'WARN', formula: 'buffer 3-7d last day' },
		{ key: 'safe', label: 'SAFE', formula: 'buffer>=7d last day' },
	]}
	{@const fmtN = (v: number) => v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(1)+'K' : v.toFixed(0)}

	<!-- 3-Level Summary Tables: Group → Company → Segment -->
	{#each [
		{ label: 'GROUP SUMMARY', data: groupAgg, dlName: 'Group Summary', color: '#383832', showSC: false },
		{ label: 'COMPANY SUMMARY', data: companyAgg, dlName: 'Company Summary', color: '#006f7c', showSC: false },
		{ label: 'SEGMENT SUMMARY', data: segmentAgg, dlName: 'Segment Summary', color: '#9d4867', showSC: true },
	] as level}
		{@const cols = level.showSC ? baseCols : baseCols.filter(c => c.key !== 'sector' && c.key !== 'company')}
		{#if level.data.length > 0}
			<div class="mb-4 overflow-x-auto" style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
				<div class="px-4 py-2 font-black uppercase tracking-wider text-sm flex items-center justify-between" style="background: {level.color}; color: #feffd6;">
					<span>{level.label}</span>
					<button onclick={() => downloadExcel(
						level.data.map(([name, d]: [string, any]) => {
							const row: any = { name, sector: [...d.sectors].join(', '), company: [...d.companies].join(', '), outlets: d.count };
							const n = d.count || 1;
							row.avg_price = Math.round(d.sumPrice / n); row.avg_blackout = Math.round(d.sumBO / n * 10)/10;
							row.avg_exp_pct = Math.round(d.sumExp / n * 100)/100; row.avg_buffer = Math.round((d.sumBurn > 0 ? d.sumTank / d.sumBurn : 0) * 10)/10;
							row.total_sales = Math.round(d.sumSales); row.total_diesel_cost = Math.round(d.sumCost);
							row.avg_margin = Math.round(d.sumMargin / n * 10)/10; row.total_tank = Math.round(d.sumTank);
							row.total_burn_day = Math.round(d.sumBurn); row.critical = d.crit; row.warning = d.warn; row.safe = d.safe;
							return row;
						}), level.dlName
					)}
						class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
						style="color: #00fc40;">
						<span class="material-symbols-outlined text-sm">download</span> EXCEL
					</button>
				</div>
				<table class="w-full text-xs">
					<thead class="sticky top-0 z-10">
						<tr style="background: #ebe8dd;">
							{#each cols as col}
								<th class="{col.key === 'name' ? 'text-left' : 'text-center'} pt-2 px-2 font-black uppercase"
									style="border-bottom: 0; {col.key === 'crit' ? 'color:#be2d06' : col.key === 'warn' ? 'color:#ff9d00' : col.key === 'safe' ? 'color:#007518' : ''}"
									>{col.label}</th>
							{/each}
						</tr>
						<tr style="background: #ebe8dd;">
							{#each cols as col}
								<th class="{col.key === 'name' ? 'text-left' : 'text-center'} pb-2 px-2 font-normal text-[7px]"
									style="border-bottom: 2px solid #383832; color: #65655e; font-style: italic;"
									>{col.formula}</th>
							{/each}
						</tr>
					</thead>
					<tbody>
						{#each level.data as [name, d], i}
							{@const n = d.count || 1}
							{@const avgBuf = d.sumBurn > 0 ? d.sumTank / d.sumBurn : 0}
							{@const bufColor = avgBuf >= 7 ? '#007518' : avgBuf >= 3 ? '#ff9d00' : '#be2d06'}
							<tr style="background: {i % 2 ? '#f6f4e9' : 'white'}; border-bottom: 1px solid #ebe8dd;">
								<td class="py-2 px-2 font-bold" style="color: #383832;">{name}</td>
								{#if level.showSC}
									<td class="py-2 px-2 text-center text-[10px]" style="color: #006f7c;">{[...d.sectors].join(', ')}</td>
									<td class="py-2 px-2 text-center text-[10px]" style="color: #65655e;">{[...d.companies].join(', ')}</td>
								{/if}
								<td class="py-2 px-2 text-center font-black">{d.count}</td>
								<td class="py-2 px-2 text-center font-mono">{fmtN(d.sumPrice / n)}</td>
								<td class="py-2 px-2 text-center font-mono">{d.boCount > 0 ? (d.sumBO / d.boCount).toFixed(1) : 'N/A'}</td>
								<td class="py-2 px-2 text-center font-mono">{(d.sumExp / n).toFixed(2)}%</td>
								<td class="py-2 px-2 text-center font-bold" style="color: {bufColor};">{avgBuf.toFixed(1)}d</td>
								<td class="py-2 px-2 text-center font-mono">{fmtN(d.sumSales)}</td>
								<td class="py-2 px-2 text-center font-mono">{fmtN(d.sumCost)}</td>
								<td class="py-2 px-2 text-center font-mono">{(d.sumMargin / n).toFixed(1)}%</td>
								<td class="py-2 px-2 text-center font-mono">{fmtN(d.sumTank)}</td>
								<td class="py-2 px-2 text-center font-mono">{fmtN(d.sumBurn)}</td>
								<td class="py-2 px-2 text-center font-mono">{fmtN(d.sumTotalFuel)}</td>
								<td class="py-2 px-2 text-center font-mono">{fmtN(d.sumTotalGenHr)}</td>
								<td class="py-2 px-2 text-center font-black" style="color: {d.crit > 0 ? '#be2d06' : '#65655e'};">{d.crit}</td>
								<td class="py-2 px-2 text-center font-black" style="color: {d.warn > 0 ? '#ff9d00' : '#65655e'};">{d.warn}</td>
								<td class="py-2 px-2 text-center font-black" style="color: {d.safe > 0 ? '#007518' : '#65655e'};">{d.safe}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/each}

	<div
		class="overflow-hidden"
		style="background: white; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;"
	>
		<div class="px-3 py-2 flex items-center gap-2" style="background: #ebe8dd; border-bottom: 1px solid #383832;">
			<span class="material-symbols-outlined text-sm" style="color: #65655e;">search</span>
			<input type="text" bind:value={search} placeholder="QUICK_SEARCH..."
				class="flex-1 px-2 py-1 text-xs font-mono uppercase"
				style="background: white; border: 1px solid #383832; color: #383832;" />
		</div>
		<div
			class="px-4 py-2 font-black uppercase tracking-wider text-sm flex items-center justify-between"
			style="background: #383832; color: #feffd6;"
		>
			<span>SECTOR_SITES</span>
			<button onclick={() => downloadExcel(filteredSites, 'Sector Sites', { statusColumns: ['action'] })}
				class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
				style="color: #00fc40;">
				<span class="material-symbols-outlined text-sm">download</span> EXCEL
			</button>
		</div>
		<div class="overflow-x-auto overflow-y-auto" style="max-height: 600px;">
			<table class="w-full text-xs">
				<thead class="sticky top-0 z-10">
					<tr style="background: #ebe8dd;">
						{#each siteCols as col}
							<th class="text-{col.align} pt-2 px-2 font-black uppercase" style="border-bottom: 0;">{col.label}</th>
						{/each}
					</tr>
					<tr style="background: #ebe8dd;">
						{#each siteCols as col}
							<th class="text-{col.align} pb-2 px-2 font-normal text-[7px]" style="border-bottom: 2px solid #383832; color: #65655e; font-style: italic;">{col.formula}</th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each filteredSites as s, i}
						{@const rowIdx = i}
						<tr
							style="background: {rowIdx % 2 === 0
								? 'white'
								: '#f6f4e9'}; border-bottom: 1px solid #ebe8dd;"
						>
							<td class="py-2 px-2 font-bold" style="color: #383832;">{s.site_id}</td>
							<td class="py-2 px-2 font-mono text-xs" style="color: #383832;">{s.site_code || s.region || ''}</td>
							<td class="py-2 px-2 text-xs" style="color: #383832;">{s.segment_name || ''}</td>
							<td class="py-2 px-2 text-center text-xs font-mono">{s.store_size || ''}</td>
							<td class="py-2 px-2 text-center font-mono">{icon(s.price||0,[3500,5000,8000],true)} {fmt(s.price||0)}</td>
							<td class="py-2 px-2 text-center font-mono">{icon(s.blackout_hr||0,[4,8,12],true)} {fmtDec(s.blackout_hr||0)}</td>
							<td class="py-2 px-2 text-center font-mono">{icon(s.buffer_days||0,[7,5,3])} {fmtDec(s.buffer_days||0)}</td>
							<td class="py-2 px-2 text-center font-mono">{fmt(s.tank||0)}</td>
							<td class="py-2 px-2 text-center font-mono">{fmt(s.daily_fuel||0)}</td>
							<td class="py-2 px-2 text-center font-mono">{fmt(s.last_day_sales||0)}</td>
							<td class="py-2 px-2 text-center font-mono">{fmt(s.avg3d_sales||0)}</td>
							<td class="py-2 px-2 text-center font-mono">{fmt(s.daily_sales||0)}</td>
							<td class="py-2 px-2 text-center font-mono">{fmt(s.last_day_fuel_cost||s.daily_cost||0)}</td>
							<td class="py-2 px-2 text-center font-mono">{fmt(s.avg3d_fuel_cost||0)}</td>
							<td class="py-2 px-2 text-center font-mono">{fmt(s.daily_cost||0)}</td>
							<td class="py-2 px-2 text-center font-mono" style="color: {(s.exp_pct_last_day||0) > 5 ? '#be2d06' : '#383832'};">{icon(s.exp_pct_last_day||0,[0.9,1.5,3],true)} {fmtDec(s.exp_pct_last_day||s.exp_pct||0,2)}%</td>
							<td class="py-2 px-2 text-center font-mono">{fmtDec(s.exp_pct_3d||0,2)}%</td>
							<td class="py-2 px-2 text-center font-mono">{fmtDec(s.exp_pct_total||0,2)}%</td>
							<td class="py-2 px-2 text-center font-mono">{fmtDec(s.margin_pct||0)}%</td>
							<td class="py-2 px-2 text-center font-mono">{fmtDec(s.margin_pct_last_day||0)}%</td>
							<td class="py-2 px-2 text-center font-mono">{fmtDec(s.margin_pct_3d||0)}%</td>
							<td class="py-2 px-2 text-center">
								<span class="inline-block px-2 py-0.5 rounded text-[10px] font-black uppercase text-white"
									style="background: {actionColors[s.action] || '#65655e'};">{s.action || '—'}</span>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<!-- Legend -->
		<div
			class="px-4 py-2 flex gap-4 text-[10px]"
			style="background: #ebe8dd; border-top: 1px solid #383832; color: #65655e;"
		>
			<span>{'\u{1F7E2}'} Good</span>
			<span>{'\u{1F7E1}'} Watch</span>
			<span>{'\u{1F7E0}'} Warning</span>
			<span>{'\u{1F534}'} Danger</span>
			<span class="ml-auto text-[9px]"
				>Price: &lt;3.5K/5K/8K | Blackout: &lt;4/8/12h | Exp%: &lt;0.9/1.5/3 | Buffer:
				&gt;7/5/3d</span
			>
		</div>
	</div>
{/if}
