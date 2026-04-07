<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { api } from '$lib/api';
	import DatePicker from '$lib/components/DatePicker.svelte';
	import KpiCard from '$lib/components/KpiCard.svelte';
	import MiniChart from '$lib/components/MiniChart.svelte';
	import TrendCharts from '$lib/components/sections/TrendCharts.svelte';
	import RollingCharts from '$lib/components/sections/RollingCharts.svelte';
	import GroupExtras from '$lib/components/sections/GroupExtras.svelte';
	import OperationsTables from '$lib/components/sections/OperationsTables.svelte';
	import Predictions from '$lib/components/sections/Predictions.svelte';
	import Rankings from '$lib/components/sections/Rankings.svelte';
	import LngComparison from '$lib/components/sections/LngComparison.svelte';
	import WhatIf from '$lib/components/sections/WhatIf.svelte';
	import SectorHeatmap from '$lib/components/sections/SectorHeatmap.svelte';
	import AiInsights from '$lib/components/sections/AiInsights.svelte';
	import OperatingModes from '$lib/components/sections/OperatingModes.svelte';
	import RiskPanel from '$lib/components/sections/RiskPanel.svelte';
	import FuelIntel from '$lib/components/sections/FuelIntel.svelte';
	import SectorSites from '$lib/components/sections/SectorSites.svelte';
	import SiteModal from '$lib/components/SiteModal.svelte';
	import Dictionary from '$lib/components/sections/Dictionary.svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';

	let showSiteModal = $state(false);
	let showComparison = $state(false);
	let showFilters = $state(false);
	let modalSiteId = $state('');
	let heatmapRows: any[] = $state([]);
	let dashSection = $state('overview');
	let comparison: any[] = $state([]);
	let periodKpis: any = $state({ last_day: null, last_3d: null });
	let monthlySummary: any[] = $state([]);
	let blackoutCalendar: any[] = $state([]);
	let transferData: any[] = $state([]);

	const dashTabs = [
		{ id: 'overview', label: 'OVERVIEW', icon: 'dashboard', sub: 'KPIs & Status', step: '01' },
		{ id: 'trends', label: 'WHAT HAPPENED', icon: 'history', sub: 'Trends & Patterns', step: '02' },
		{ id: 'sector', label: 'WHERE', icon: 'map', sub: 'Sectors & Sites', step: '03' },
		{ id: 'operations', label: 'HOW WE RAN', icon: 'precision_manufacturing', sub: 'Operations & Fleet', step: '04' },
		{ id: 'risk', label: 'WHAT\'S AT RISK', icon: 'warning', sub: 'Alerts & Scores', step: '05' },
		{ id: 'fuel', label: 'FUEL & COST', icon: 'local_gas_station', sub: 'Intel & Budget', step: '06' },
		{ id: 'predictions', label: 'WHAT\'S NEXT', icon: 'query_stats', sub: 'Forecast & Actions', step: '07' },
		{ id: 'ai', label: 'ASK AI', icon: 'psychology', sub: 'Chat & Insights', step: '08' },
	];

	// Filter state
	let sector = $state('All Sectors');
	let company = $state('All Companies');
	let siteId = $state('All Sites');
	let selectedSites: string[] = $state([]);
	let siteDropOpen = $state(false);
	let siteType = $state('All');

	// Default 60 days
	const _defaultEnd = new Date();
	const _defaultStart = new Date(); _defaultStart.setDate(_defaultStart.getDate() - 60);
	let dateFrom = $state(_defaultStart.toISOString().slice(0, 10));
	let dateTo = $state(_defaultEnd.toISOString().slice(0, 10));

	function quickDate(days: number) {
		const end = new Date();
		dateTo = end.toISOString().slice(0, 10);
		if (days === 0) { dateFrom = dateTo; }
		else if (days < 0) { dateFrom = ''; dateTo = ''; }
		else { const s = new Date(); s.setDate(s.getDate() - days); dateFrom = s.toISOString().slice(0, 10); }
	}

	function resetFilters() {
		sector = 'All Sectors';
		company = 'All Companies';
		activeCompany = 'All';
		selectedSites = [];
		siteType = 'All';
		quickDate(60);
	}

	// Sector friendly names for Layer 1 pills
	const sectorOptions = [
		{ label: 'Group', value: '' },
		{ label: 'Distribution', value: 'PG' },
		{ label: 'F&B', value: 'CFC' },
		{ label: 'Property', value: 'CP' },
		{ label: 'Retail', value: 'CMHL' },
	];

	// Active company filter
	let activeCompany = $state('All');

	// Derived: companies from actual data
	function availableCompanies(): string[] {
		let pool = econ;
		if (sector !== 'All Sectors') pool = pool.filter((e: any) => e.sector_id === sector);
		return [...new Set(pool.map((e: any) => e.company).filter(Boolean))].sort();
	}

	// Derived: sites for selected sector + company (with name + code)
	function availableSites(): { id: string; name: string; code: string }[] {
		let pool = econ;
		if (sector !== 'All Sectors') pool = pool.filter((e: any) => e.sector_id === sector);
		if (activeCompany !== 'All') pool = pool.filter((e: any) => e.company === activeCompany);
		const seen = new Set<string>();
		return pool.filter((e: any) => { if (!e.site_id || seen.has(e.site_id)) return false; seen.add(e.site_id); return true; })
			.map((e: any) => ({ id: e.site_id, name: e.site_name || e.cost_center_description || '', code: e.site_code || e.region || '' }))
			.sort((a, b) => a.name.localeCompare(b.name));
	}

	function isDictionary() { return page.url.searchParams.get('view') === 'dictionary'; }

	// Data
	let loading = $state(true);
	let error = $state('');
	let econ: any[] = $state([]);
	let sectors: string[] = $state([]);
	let companies: string[] = $state([]);
	let sites: string[] = $state([]);

	// Build sector options dynamically from data
	let dynamicSectorOptions: { label: string; value: string }[] = $state([]);

	async function fetchData() {
		loading = true;
		error = '';
		try {
			const p = new URLSearchParams();
			if (dateFrom) p.set('date_from', dateFrom);
			if (dateTo) p.set('date_to', dateTo);
			econ = await api.get(`/economics?${p}`);
			sectors = [...new Set(econ.map((e: any) => e.sector_id).filter(Boolean))].sort();

			// Build sector options from data: use business_sector as label if available
			const sectorMap = new Map<string, string>();
			for (const e of econ) {
				if (e.sector_id && !sectorMap.has(e.sector_id)) {
					sectorMap.set(e.sector_id, e.business_sector || e.sector_id);
				}
			}
			dynamicSectorOptions = [
				{ label: 'Group', value: 'All Sectors' },
				...Array.from(sectorMap.entries()).sort().map(([id, biz]) => ({
					label: `${biz} (${id})`, value: id
				})),
			];
			// Fetch yesterday vs 3-day comparison + period KPIs (with sector filter)
			try {
				let effSector = sector !== 'All Sectors' ? sector : '';
				if (!effSector && activeCompany !== 'All') {
					const m = econ.find((e: any) => e.company === activeCompany);
					if (m) effSector = m.sector_id || '';
				}
				const sp = effSector ? `?sector=${effSector}` : '';
				const dtParam = dateTo ? `${sp ? '&' : '?'}date_to=${dateTo}` : '';
				const [c, pk, ms, bc, tr] = await Promise.all([
					api.get('/yesterday-comparison'),
					api.get(`/period-kpis${sp}${dtParam}`),
					api.get(`/monthly-summary${sp}`).catch(() => []),
					api.get(`/blackout-calendar${sp}`).catch(() => ({ days: [] })),
					api.get('/transfers').catch(() => ({ transfers: [] })),
				]);
				comparison = c.metrics || [];
				periodKpis = pk;
				monthlySummary = ms || [];
				blackoutCalendar = bc?.days || [];
				transferData = (tr?.transfers || []);
			} catch {}
		} catch (e) { console.error(e); error = 'Failed to load dashboard data. Check your connection and try again.'; }
		finally { loading = false; }
	}

	// Reset cascading filters + re-fetch period KPIs on sector change
	$effect(() => { sector; activeCompany = 'All'; company = 'All Companies'; siteId = 'All Sites'; selectedSites = []; });
	$effect(() => { activeCompany; selectedSites = []; });
	$effect(() => {
		// Re-fetch period KPIs when sector or company changes
		const s = sector;
		const c = activeCompany;
		if (!loading) {
			// Determine effective sector: if company is selected, find its sector from econ data
			let effectiveSector = s !== 'All Sectors' ? s : '';
			if (!effectiveSector && c !== 'All') {
				const match = econ.find((e: any) => e.company === c);
				if (match) effectiveSector = match.sector_id || '';
			}
			const sp = effectiveSector ? `?sector=${effectiveSector}` : '';
			const dt2 = dateTo ? `${sp ? '&' : '?'}date_to=${dateTo}` : '';
			api.get(`/period-kpis${sp}${dt2}`).then(pk => { periodKpis = pk; }).catch(() => {});
		}
	});

	// Auto-refetch when date range changes
	let _prevDateKey = '';
	$effect(() => {
		const key = `${dateFrom}|${dateTo}`;
		if (key !== _prevDateKey && _prevDateKey !== '') {
			fetchData();
		}
		_prevDateKey = key;
	});

	function syncURL() {
		const p = new URLSearchParams();
		if (sector !== 'All Sectors') p.set('sector', sector);
		if (activeCompany !== 'All') p.set('company', activeCompany);
		if (siteType !== 'All') p.set('type', siteType);
		if (dateFrom) p.set('from', dateFrom);
		if (dateTo) p.set('to', dateTo);
		if (dashSection !== 'trends') p.set('tab', dashSection);
		const url = p.toString() ? `?${p}` : window.location.pathname;
		window.history.replaceState({}, '', url);
	}

	$effect(() => { sector; activeCompany; siteType; dateFrom; dateTo; dashSection; syncURL(); });

	onMount(() => {
		const params = page.url.searchParams;
		if (params.get('sector')) sector = params.get('sector')!;
		if (params.get('company')) activeCompany = params.get('company')!;
		if (params.get('type')) siteType = params.get('type')!;
		if (params.get('from')) dateFrom = params.get('from')!;
		if (params.get('to')) dateTo = params.get('to')!;
		if (params.get('tab')) dashSection = params.get('tab')!;
		fetchData();
	});

	function filtered() {
		let f = econ;
		if (sector !== 'All Sectors') f = f.filter((e: any) => e.sector_id === sector);
		if (activeCompany !== 'All') f = f.filter((e: any) => e.company === activeCompany);
		if (selectedSites.length > 0) f = f.filter((e: any) => selectedSites.includes(e.site_id));
		if (siteType !== 'All') f = f.filter((e: any) => e.site_type === siteType);
		return f;
	}

	function sectorApiParam(): string {
		return sector !== 'All Sectors' ? sector : '';
	}

	function kpis(data: any[]) {
		if (!data.length) return null;
		const wb = data.filter((e: any) => e.avg_daily_liters > 0);
		const wt = wb.filter((e: any) => e.diesel_available > 0);
		const tank = wt.reduce((s: number, e: any) => s + (e.diesel_available || 0), 0);
		const burn = wb.reduce((s: number, e: any) => s + (e.avg_daily_liters || 0), 0);
		const buffer = burn > 0 ? tank / burn : 0;
		const cost = data.reduce((s: number, e: any) => s + (e.energy_cost || 0), 0);
		const crit = wt.filter((e: any) => e.latest_buffer_days < 3).length;
		const warn = wt.filter((e: any) => e.latest_buffer_days >= 3 && e.latest_buffer_days < 7).length;
		const safe = wt.filter((e: any) => e.latest_buffer_days >= 7).length;
		const noData = data.filter((e: any) => !e.diesel_available && !e.avg_daily_liters).length;
		const total = data.length;
		const pct = total > 0 ? Math.round(safe / total * 100) : 0;
		const needed = wt.filter((e: any) => (e.latest_buffer_days || 0) < 7).reduce((s: number, e: any) => s + Math.max(0, 7 * (e.avg_daily_liters || 0) - (e.diesel_available || 0)), 0);
		const sales = data.reduce((s: number, e: any) => s + (e.total_sales || 0), 0);
		const dieselPct = sales > 0 ? (cost / sales * 100) : 0;
		const genHours = data.reduce((s: number, e: any) => s + (e.total_gen_hours || 0), 0);
		return { tank, burn, buffer, cost, crit, warn, safe, noData, total, pct, needed, sales, dieselPct, genHours };
	}

	function fmt(v: number, type = 'num'): string {
		if (type === 'M') return (v / 1e6).toFixed(1) + 'M';
		if (type === 'K') return (v / 1e3).toFixed(1) + 'k';
		if (type === 'd') return v.toFixed(1);
		return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
	}

	function compareData() {
		if (selectedSites.length !== 2) return [];
		const s1 = econ.find((e: any) => e.site_id === selectedSites[0]);
		const s2 = econ.find((e: any) => e.site_id === selectedSites[1]);
		if (!s1 || !s2) return [];

		const metrics = [
			{ name: 'Buffer Days', v1: s1.latest_buffer_days, v2: s2.latest_buffer_days, higher: true },
			{ name: 'Tank (L)', v1: s1.diesel_available, v2: s2.diesel_available, higher: true },
			{ name: 'Daily Burn (L)', v1: s1.avg_daily_liters, v2: s2.avg_daily_liters, higher: false },
			{ name: 'Gen Hours', v1: s1.total_gen_hours, v2: s2.total_gen_hours, higher: false },
			{ name: 'Efficiency L/Hr', v1: s1.avg_daily_liters && s1.total_gen_hours ? s1.avg_daily_liters / s1.total_gen_hours : 0, v2: s2.avg_daily_liters && s2.total_gen_hours ? s2.avg_daily_liters / s2.total_gen_hours : 0, higher: false },
			{ name: 'Energy Cost', v1: s1.energy_cost, v2: s2.energy_cost, higher: false },
			{ name: 'Total Sales', v1: s1.total_sales, v2: s2.total_sales, higher: true },
			{ name: 'Diesel %', v1: s1.diesel_pct, v2: s2.diesel_pct, higher: false },
		];
		return metrics;
	}

	function handleKeydown(e: KeyboardEvent) {
		// Don't capture when typing in inputs
		if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return;

		// 1-7: Switch tabs
		const num = parseInt(e.key);
		if (num >= 1 && num <= 7 && !e.ctrlKey && !e.metaKey && !e.altKey) {
			const tab = dashTabs[num - 1];
			if (tab) dashSection = tab.id;
			return;
		}

		// Ctrl+K or Cmd+K: Focus search (if it exists in header)
		if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
			e.preventDefault();
			const searchBtn = document.querySelector('[data-search-toggle]') as HTMLButtonElement;
			if (searchBtn) searchBtn.click();
		}

		// Escape: Close modals
		if (e.key === 'Escape') {
			if (showSiteModal) { showSiteModal = false; return; }
		}
	}

	$effect(() => { page.url.searchParams; });

	if (typeof window !== 'undefined') window.addEventListener('keydown', handleKeydown);
	onDestroy(() => { if (typeof window !== 'undefined') window.removeEventListener('keydown', handleKeydown); });
</script>

<!-- Filter Bar: Sticky below header -->
<section class="p-4 sticky top-16 z-30" style="background: #f6f4e9; border-bottom: 3px solid #383832; box-shadow: 0 4px 8px rgba(56,56,50,0.15);">
	<!-- Mobile filter toggle -->
	<button onclick={() => showFilters = !showFilters}
		class="md:hidden px-3 py-1.5 text-[10px] font-black uppercase flex items-center gap-1 mb-2"
		style="background: #383832; color: #feffd6;">
		<span class="material-symbols-outlined text-sm">tune</span>
		{showFilters ? 'HIDE FILTERS' : 'SHOW FILTERS'}
	</button>
	<div class="{showFilters ? 'flex' : 'hidden'} md:flex flex-wrap items-end gap-4">
		<!-- Sector -->
		<div class="flex-1 min-w-[140px]">
			<div class="inline-block px-2 py-0.5 text-[9px] font-black uppercase mb-1" style="background: #383832; color: #feffd6;">SECTOR</div>
			<select bind:value={sector} class="w-full px-3 py-2 text-sm font-bold uppercase" style="background: white; border: 2px solid #383832; color: #383832;">
				{#each dynamicSectorOptions as opt}
					<option value={opt.value}>{opt.label}</option>
				{/each}
				{#if dynamicSectorOptions.length === 0}
					<option value="All Sectors">Group</option>
				{/if}
			</select>
		</div>

		<!-- Company (disabled when Group selected) -->
		<div class="flex-1 min-w-[140px]">
			<div class="inline-block px-2 py-0.5 text-[9px] font-black uppercase mb-1" style="background: #383832; color: #feffd6;">COMPANY</div>
			<select bind:value={activeCompany}
				disabled={sector === 'All Sectors'}
				class="w-full px-3 py-2 text-sm font-bold uppercase"
				style="background: {sector === 'All Sectors' ? '#ebe8dd' : 'white'}; border: 2px solid #383832; color: {sector === 'All Sectors' ? '#65655e' : '#383832'}; {sector === 'All Sectors' ? 'cursor: not-allowed;' : ''}">
				<option value="All">All Companies</option>
				{#each availableCompanies() as c}<option value={c}>{c}</option>{/each}
			</select>
		</div>

		<!-- Site (disabled when Group selected and no company chosen) -->
		{#if true}
		{@const siteList = availableSites()}
		{@const siteDisabled = sector === 'All Sectors' && activeCompany === 'All'}
		<div class="flex-1 min-w-[180px] relative">
			<div class="inline-block px-2 py-0.5 text-[9px] font-black uppercase mb-1" style="background: #383832; color: #feffd6;">SITE_ID</div>
			<button onclick={() => { if (!siteDisabled) siteDropOpen = !siteDropOpen; }}
				class="w-full flex items-center gap-2 px-3 py-2 text-sm font-bold uppercase text-left"
				style="background: {siteDisabled ? '#ebe8dd' : 'white'}; border: 2px solid #383832; color: {siteDisabled ? '#65655e' : '#383832'}; {siteDisabled ? 'cursor: not-allowed;' : ''}">
				<span class="flex-1 truncate">{selectedSites.length === 0 ? 'ALL SITES' : selectedSites.length === 1 ? (siteList.find(s => s.id === selectedSites[0])?.name || selectedSites[0]) : selectedSites.length + ' SELECTED'}</span>
				<span class="text-[8px]">{siteDropOpen ? '▲' : '▼'}</span>
			</button>

			{#if siteDropOpen}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div class="fixed inset-0 z-40" onclick={() => siteDropOpen = false}></div>
				<div class="absolute top-full left-0 z-50 mt-1 w-full max-h-[300px] overflow-y-auto" style="background: white; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
					<!-- Select All / Clear -->
					<div class="flex gap-2 p-2" style="border-bottom: 1px solid #ebe8dd;">
						<button onclick={() => { selectedSites = siteList.map(s => s.id); }} class="text-[10px] font-bold uppercase" style="color: #007518;">SELECT ALL</button>
						<span style="color: #ebe8dd;">|</span>
						<button onclick={() => { selectedSites = []; }} class="text-[10px] font-bold uppercase" style="color: #be2d06;">CLEAR</button>
						<span class="text-[9px] ml-auto" style="color: #65655e;">{siteList.length} sites</span>
					</div>
					{#each siteList as s}
						<label class="flex items-center gap-2 px-3 py-1.5 text-xs cursor-pointer transition-colors hover:bg-[#f6f4e9]" style="color: #383832;">
							<input type="checkbox" checked={selectedSites.includes(s.id)}
								onchange={() => {
									if (selectedSites.includes(s.id)) selectedSites = selectedSites.filter(x => x !== s.id);
									else selectedSites = [...selectedSites, s.id];
								}}
								style="accent-color: #007518;" />
							<span class="font-bold">{s.name}</span>
							<span class="text-[9px] ml-auto font-mono" style="color: #65655e;">{s.code || s.id}</span>
						</label>
					{/each}
				</div>
			{/if}
		</div>

		<!-- Site Type -->
		<div class="min-w-[100px]">
			<div class="inline-block px-2 py-0.5 text-[9px] font-black uppercase mb-1" style="background: #383832; color: #feffd6;">TYPE</div>
			<select bind:value={siteType} class="w-full px-3 py-2 text-sm font-bold uppercase" style="background: white; border: 2px solid #383832; color: #383832;">
				<option value="All">ALL</option>
				<option value="Regular">REGULAR</option>
				<option value="LNG">LNG</option>
			</select>
		</div>

		<!-- Date Range -->
		<div class="flex-1 min-w-[180px]">
			<div class="inline-block px-2 py-0.5 text-[9px] font-black uppercase mb-1" style="background: #383832; color: #feffd6;">DATE_RANGE</div>
			<DatePicker bind:from={dateFrom} bind:to={dateTo} />
		</div>

		<!-- RESET Button -->
		<div class="flex items-end">
			<button onclick={resetFilters}
				class="px-6 py-2 text-xs font-black uppercase active:translate-x-[1px] active:translate-y-[1px] flex items-center gap-1.5"
				style="background: #be2d06; border: 2px solid #383832; color: #feffd6; box-shadow: 4px 4px 0px 0px #383832;">
				<span class="material-symbols-outlined text-sm">restart_alt</span>
				RESET
			</button>
		</div>
		{/if}

		<!-- Deep Dive button (when exactly 1 site selected) -->
		{#if selectedSites.length === 1}
			<button onclick={() => { modalSiteId = selectedSites[0]; showSiteModal = true; }}
				class="px-5 py-2 text-xs font-black uppercase active:translate-x-[1px] active:translate-y-[1px]"
				style="background: #00fc40; border: 2px solid #383832; color: #383832; box-shadow: 4px 4px 0px 0px #383832;">
				DEEP_DIVE
			</button>
		{/if}

		<!-- Compare button (when exactly 2 sites selected) -->
		{#if selectedSites.length === 2}
			<button onclick={() => showComparison = true}
				class="px-5 py-2 text-xs font-black uppercase active:translate-x-[1px] active:translate-y-[1px]"
				style="background: #006f7c; border: 2px solid #383832; color: white; box-shadow: 4px 4px 0px 0px #383832;">
				COMPARE
			</button>
		{/if}
	</div>
</section>

{#if isDictionary()}
	<Dictionary />
{:else if loading}
	<div class="text-center py-20">
		<span class="material-symbols-outlined text-4xl animate-pulse" style="color: #007518;">bolt</span>
		<p class="font-bold mt-3 uppercase tracking-widest text-sm" style="color: #383832;">INITIALIZING_COMMAND_CENTER...</p>
	</div>
{:else if error}
	<div class="text-center py-20">
		<span class="material-symbols-outlined text-4xl" style="color: #be2d06;">error</span>
		<p class="font-bold mt-3 uppercase tracking-widest text-sm" style="color: #be2d06;">{error}</p>
		<button onclick={fetchData} class="mt-4 px-6 py-2 text-xs font-black uppercase"
			style="background: #383832; color: #feffd6; border: 2px solid #383832;">
			<span class="material-symbols-outlined text-sm align-middle">refresh</span> RETRY
		</button>
	</div>
{:else}
	{@const data = filtered()}
	{@const k = kpis(data)}

	{#if k}
		<!-- ═══ STORY TABS ═══ -->
		<div class="mb-6">
			<!-- Story Flow Bar -->
			<div class="overflow-x-auto">
			<div class="flex items-stretch min-w-[700px]" style="border: 3px solid #383832; border-bottom: 0;">
				{#each dashTabs as tab, idx}
					{@const active = dashSection === tab.id}
					{@const stepIdx = dashTabs.findIndex(t => t.id === dashSection)}
					{@const isPast = idx < stepIdx}
					<button
						onclick={() => dashSection = tab.id}
						class="flex-1 px-2 py-3 flex flex-col items-center justify-center gap-0.5 transition-all relative"
						style="{active
							? 'background: #383832; color: #feffd6;'
							: isPast
								? 'background: #007518; color: white;'
								: 'background: #f6f4e9; color: #383832; border-right: 1px solid #383832;'}"
					>
						<!-- Step number -->
						<span class="text-[8px] font-black tracking-widest opacity-60">{tab.step}</span>
						<!-- Icon -->
						<span class="material-symbols-outlined {active ? 'text-lg' : 'text-base'}" style="{active ? 'color: #00fc40;' : ''}">{tab.icon}</span>
						<!-- Label -->
						<span class="text-[10px] font-black uppercase leading-tight">{tab.label}</span>
						<span class="text-[7px] uppercase opacity-60 leading-tight">{tab.sub}</span>
						<!-- Active indicator -->
						{#if active}
							<div class="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-full w-0 h-0" style="border-left: 8px solid transparent; border-right: 8px solid transparent; border-top: 8px solid #383832;"></div>
						{/if}
						<!-- Connector arrow between tabs -->
						{#if idx < dashTabs.length - 1 && !active}
							<div class="absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/2 z-10 text-[8px] font-black" style="color: {isPast ? 'white' : '#65655e'};">→</div>
						{/if}
					</button>
				{/each}
				<!-- Site Deep Dive -->
				{#if sites.length > 0}
					<button
						onclick={() => { modalSiteId = sites[0]; showSiteModal = true; }}
						class="px-4 py-3 flex flex-col items-center justify-center gap-0.5"
						style="background: #00fc40; color: #383832;"
					>
						<span class="text-[8px] font-black tracking-widest opacity-60">++</span>
						<span class="material-symbols-outlined text-base">search</span>
						<span class="text-[10px] font-black uppercase">SITE DIVE</span>
						<span class="text-[7px] uppercase opacity-60">Deep Analysis</span>
					</button>
				{/if}
			</div>
			<div class="text-[8px] font-mono px-2 py-1 text-right" style="color: #65655e;">
				KEYS: 1-7 switch tab | ESC close modal
			</div>
			</div>

			<!-- Story chapter intro -->
			{#each dashTabs.filter(t => t.id === dashSection) as currentTab}
				<div class="flex items-center gap-3 px-5 py-2.5" style="background: #383832; color: #feffd6; border-left: 3px solid #383832; border-right: 3px solid #383832;">
					<span class="text-2xl font-black" style="color: #00fc40;">{currentTab.step}</span>
					<div>
						<span class="text-sm font-black uppercase">{currentTab.label}</span>
						<span class="text-[10px] ml-2 opacity-60">— {currentTab.sub}</span>
					</div>
				</div>
			{/each}

			<!-- Tab Content -->
			<div class="p-4" style="border: 3px solid #383832; border-top: 0; min-height: 400px;">
				{#if dashSection === 'overview'}
				{@const ld = periodKpis.last_day}
				{@const td = periodKpis.last_3d}
				{@const opModes = periodKpis.operating_modes || { OPEN: 0, MONITOR: 0, REDUCE: 0, CLOSE: 0 }}
				{@const sectorSnap = periodKpis.sector_snapshot || []}
				<div class="space-y-4">

					<!-- ═══ UNIFIED COCKPIT: LATEST vs 3D ═══ -->
					{#if ld}
						{@const bc1 = ld.buffer >= 7 ? '#007518' : ld.buffer >= 3 ? '#ff9d00' : '#be2d06'}
						{@const bl1 = ld.buffer >= 7 ? 'SAFE' : ld.buffer >= 3 ? 'WARNING' : 'CRITICAL'}
						{@const daysAgo = Math.floor((Date.now() - new Date(ld.date).getTime()) / 86400000)}
						{@const ageColor = daysAgo <= 1 ? '#007518' : daysAgo <= 3 ? '#ff9d00' : '#be2d06'}
						{@const fmtV = (v: number) => v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(1)+'K' : v.toLocaleString()}
						<div style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
							<!-- Header -->
							<div class="px-4 py-2 flex justify-between items-center" style="background: #383832; color: #feffd6;">
								<span class="font-black uppercase text-sm">LATEST DATA <span class="font-normal text-[10px] opacity-75 ml-2">{ld.date} <span class="px-1.5 py-0.5 font-black" style="background: {ageColor}; color: white;">{daysAgo === 0 ? 'TODAY' : daysAgo === 1 ? 'YESTERDAY' : daysAgo + 'd AGO'}</span> | {ld.sites}/{ld.total_sites || ld.sites} sites | {ld.generators || 0} gens | {fmtV(ld.fuel_price || 0)} MMK/L</span></span>
								<span class="px-3 py-1 text-xs font-black uppercase" style="background: {bc1}; color: white;">{bl1}: {ld.buffer} DAYS</span>
							</div>

							<!-- Data quality warning -->
							{#if (ld.sites_not_reported || 0) > 0 || (ld.tank_missing || 0) > 0}
								<div class="px-4 py-1.5 text-[10px] font-bold flex gap-4" style="background: #fff3cd; border-bottom: 1px solid #383832; color: #856404;">
									{#if (ld.sites_not_reported || 0) > 0}<span>⚠️ {ld.sites_not_reported} sites did not report on {ld.date}</span>{/if}
									{#if (ld.tank_missing || 0) > 0}<span>⚠️ Tank balance missing for {ld.tank_missing} sites</span>{/if}
								</div>
							{/if}

							<!-- Buffer Hero -->
							<div class="p-6 text-center" style="background: white; border-bottom: 2px solid #383832;">
								<div class="text-5xl sm:text-7xl font-black" style="color: {bc1};">{ld.buffer}</div>
								<div class="text-lg font-bold mt-2" style="color: #383832;">DAYS OF FUEL LEFT</div>
								{#if td}
									{@const bufDiff = td.buffer ? ((ld.buffer - td.buffer) / Math.max(td.buffer, 0.1) * 100) : 0}
									<div class="text-sm font-bold mt-1" style="color: {bufDiff > 1 ? '#007518' : bufDiff < -1 ? '#be2d06' : '#65655e'};">
										{bufDiff > 1 ? '▲' : bufDiff < -1 ? '▼' : '→'} {Math.abs(bufDiff).toFixed(0)}% vs Prior 3 Days ({td.buffer}d)
									</div>
								{/if}
								<div class="mx-auto mt-3 h-4 overflow-hidden" style="background: #ebe8dd; border: 2px solid #383832; max-width: 500px;">
									<div class="h-full" style="background: {bc1}; width: {Math.min(100, ld.buffer / 20 * 100)}%;"></div>
								</div>
								<div class="text-xs mt-1" style="color: #65655e;">{Math.round(ld.buffer / 20 * 100)}% of 20-day target</div>
							</div>

							<!-- KPI Cards: Option 3 — Compact with horizontal bars -->
							<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mt-2">
								{#each [
									{ t1: ld.total_gen_hr||0, t3: td?.gen_hr||0, tl: 'GEN RUN HR', tc: 'SUM(gen_run_hr)',
									  s1: ld.gen_hr_per_site||0, s3: td?.gen_hr_per_site||0, sl: '/SITE', sdec: 1,
									  good: 'low', key: 'gen_hr', color: '#ff9d00' },
									{ t1: ld.total_fuel||ld.burn||0, t3: td?.burn||0, tl: 'FUEL USED (L)', tc: 'SUM(daily_used)',
									  s1: ld.fuel_per_site||0, s3: td?.fuel_per_site||0, sl: '/SITE', sdec: 1,
									  good: 'low', key: 'fuel', color: '#e85d04' },
									{ t1: ld.tank, t3: td?.tank||0, tl: 'TANK BAL (L)', tc: 'SUM(spare_tank)',
									  s1: ld.tank_per_site||0, s3: td?.tank_per_site||0, sl: '/SITE',
									  good: 'high', key: 'tank', color: '#007518' },
									{ t1: ld.total_blackout||0, t3: td?.total_blackout ? td.total_blackout / (td.days || 3) : 0, tl: 'BLACKOUT HR', tc: 'SUM(blackout)', tdec: 1,
									  s1: ld.blackout_per_site||ld.blackout||0, s3: td?.blackout_per_site||td?.blackout||0, sl: '/SITE', sdec: 1,
									  good: 'low', key: 'blackout', color: '#be2d06' },
									{ t1: ld.burn, t3: td?.burn||0, tl: 'BURN/DAY (L)', tc: 'SUM(used) ÷ days',
									  s1: ld.efficiency||0, s3: td?.efficiency||0, sl: 'L/HR', sdec: 1,
									  good: 'low', key: 'fuel', color: '#9d4867' },
									{ t1: ld.cost, t3: td?.cost||0, tl: 'COST (MMK)', tc: 'burn × price',
									  s1: ld.needed, s3: td?.needed||0, sl: 'NEEDED',
									  good: 'low', key: 'fuel', color: '#6d597a' },
								] as m, i}
									{@const rd = periodKpis.recent_daily || []}
									{@const tDiff = m.t3 ? ((m.t1 - m.t3) / Math.max(Math.abs(m.t3), 0.01) * 100) : 0}
									{@const tImpr = m.good === 'high' ? tDiff > 1 : tDiff < -1}
									{@const tClr = Math.abs(tDiff) < 1 ? '#65655e' : tImpr ? '#007518' : '#be2d06'}
									{@const tArr = tDiff > 1 ? '▲' : tDiff < -1 ? '▼' : '→'}
									{@const vals = rd.map((d: any) => d[m.key] || 0)}
									{@const maxVal = Math.max(...vals, 1)}
									{@const avg3 = rd.length >= 4 ? (vals[0] + vals[1] + vals[2]) / 3 : 0}
									{@const sites = rd.map((d: any) => d.sites || 1)}
									{@const avg3PerSite = rd.length >= 4 ? ((vals[0]/sites[0] + vals[1]/sites[1] + vals[2]/sites[2]) / 3) : 0}
									<div style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
										<!-- Header -->
										<div class="px-3 py-1.5 flex justify-between items-center" style="background: #383832; color: #feffd6;">
											<span class="text-[11px] font-black uppercase">{m.tl}</span>
											<span class="text-[10px] font-bold" style="color: {tClr};">{tArr}{Math.abs(tDiff).toFixed(0)}% vs 3D</span>
										</div>
										<!-- KPIs row -->
										<div class="flex">
											<div class="p-3 flex flex-col justify-center" style="flex: 1; border-right: 1px dashed #ebe8dd;">
												<div class="text-2xl font-black" style="color: #383832;">{m.tdec ? m.t1.toFixed(m.tdec) : fmtV(m.t1)}</div>
												<div class="text-[9px] font-bold" style="color: #65655e;">TOTAL</div>
												<div class="text-[8px]" style="color: #9d9d91;">3D: {m.tdec ? m.t3.toFixed(m.tdec) : fmtV(m.t3)}</div>
											</div>
											<div class="p-3 flex flex-col justify-center" style="flex: 1;">
												<div class="text-2xl font-black" style="color: #383832;">{m.sdec ? m.s1.toFixed(m.sdec) : fmtV(m.s1)}</div>
												<div class="text-[9px] font-bold" style="color: #65655e;">{m.sl}</div>
												<div class="text-[8px]" style="color: #9d9d91;">3D: {m.sdec ? m.s3.toFixed(m.sdec) : fmtV(m.s3)}</div>
											</div>
										</div>
										<!-- Horizontal bar chart with daily values -->
										<div style="border-top: 1px solid #ebe8dd;">
											{#each rd as day, di}
												{@const isLatest = di === rd.length - 1}
												{@const v = vals[di]}
												{@const pct = maxVal > 0 ? (v / maxVal * 100) : 0}
												{@const perSite = sites[di] > 0 ? v / sites[di] : 0}
												<!-- 3D avg line -->
												{#if isLatest && rd.length >= 4}
													<div class="px-3 py-0.5 flex items-center gap-2" style="border-top: 2px dashed {m.color};">
														<span class="text-[8px] font-bold" style="color: {m.color};">3D AVG: {fmtV(Math.round(avg3))} ({avg3PerSite.toFixed(1)}{m.sl})</span>
													</div>
												{/if}
												<div class="px-3 py-1 flex items-center gap-2" style="border-top: 1px solid {isLatest ? m.color : 'rgba(56,56,50,0.08)'}; {isLatest ? 'background: rgba(56,56,50,0.03);' : ''}">
													<span class="text-[9px] w-10 shrink-0 {isLatest ? 'font-black' : ''}" style="color: {isLatest ? m.color : '#828179'};">
														{day.date.slice(5)}
													</span>
													<!-- Bar -->
													<div class="flex-1 h-4 relative" style="background: #f0ede3;">
														<div class="h-full" style="width: {pct}%; background: {isLatest ? m.color : m.color + '60'};"></div>
														{#if avg3 > 0}
															<div class="absolute top-0 h-full w-px" style="left: {Math.min(avg3/maxVal*100, 100)}%; background: {m.color}; opacity: 0.5;"></div>
														{/if}
													</div>
													<span class="text-[9px] w-12 text-right shrink-0 {isLatest ? 'font-black' : ''}" style="color: #383832;">{fmtV(Math.round(v))}</span>
													<span class="text-[8px] w-12 text-right shrink-0" style="color: #9d9d91;">{perSite.toFixed(1)}{m.sl}</span>
													{#if isLatest && avg3 > 0}
														{@const vsAvg = (v - avg3) / avg3 * 100}
														{@const vClr = (m.good === 'high' ? vsAvg > 1 : vsAvg < -1) ? '#007518' : (m.good === 'high' ? vsAvg < -1 : vsAvg > 1) ? '#be2d06' : '#65655e'}
														<span class="text-[8px] font-bold w-14 text-right shrink-0" style="color: {vClr};">{vsAvg > 0 ? '▲' : vsAvg < 0 ? '▼' : '→'}{Math.abs(vsAvg).toFixed(0)}%</span>
													{:else}
														<span class="w-14 shrink-0"></span>
													{/if}
												</div>
											{/each}
										</div>
										<!-- Formula -->
										<div class="px-3 py-1 text-[8px] font-mono" style="background: #f6f4e9; color: #9d9d91; border-top: 1px solid #ebe8dd;">{m.tc}</div>
									</div>
								{/each}
							</div>

							<!-- Sales, Cost, Diesel% — same card style as KPI cards above -->
							<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
								{#each [
									{ t1: ld.has_sales ? ld.sales : 0, t3: td?.has_sales ? td.sales : 0, tl: 'SALES (MMK)', tc: 'SUM(sales_amt)',
									  s1: ld.has_sales && ld.sites > 0 ? ld.sales / ld.sites : 0, s3: td && td.has_sales && td.sites > 0 ? td.sales / td.sites : 0, sl: '/SITE', sdec: 0,
									  good: 'high', color: '#006f7c', na: !ld.has_sales },
									{ t1: ld.cost, t3: td?.cost || 0, tl: 'DIESEL COST (MMK)', tc: 'burn × fuel_price',
									  s1: ld.sites > 0 ? ld.cost / ld.sites : 0, s3: td && td.sites > 0 ? td.cost / td.sites : 0, sl: '/SITE', sdec: 0,
									  good: 'low', color: '#9d4867', na: false },
									{ t1: ld.has_sales ? ld.diesel_pct : 0, t3: td?.has_sales ? td.diesel_pct : 0, tl: 'DIESEL % OF SALES', tc: 'cost ÷ sales × 100', tdec: 2,
									  s1: 0, s3: 0, sl: '', sdec: 0, noSite: true,
									  good: 'low', color: ld.has_sales && ld.diesel_pct > 3 ? '#be2d06' : '#007518', na: !ld.has_sales },
								] as m}
									{@const tDiff = m.t3 ? ((m.t1 - m.t3) / Math.max(Math.abs(m.t3), 0.01) * 100) : 0}
									{@const tImpr = m.good === 'high' ? tDiff > 1 : tDiff < -1}
									{@const tClr = Math.abs(tDiff) < 1 ? '#65655e' : tImpr ? '#007518' : '#be2d06'}
									{@const tArr = tDiff > 1 ? '▲' : tDiff < -1 ? '▼' : '→'}
									<div style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
										<div class="px-3 py-1.5 flex justify-between items-center" style="background: #383832; color: #feffd6;">
											<span class="text-[11px] font-black uppercase">{m.tl}</span>
											{#if !m.na}
												<span class="text-[10px] font-bold" style="color: {tClr};">{tArr}{Math.abs(tDiff).toFixed(0)}% vs 3D</span>
											{/if}
										</div>
										<div class="flex">
											<div class="p-3 flex flex-col justify-center" style="flex: 1; {m.noSite ? '' : 'border-right: 1px dashed #ebe8dd;'}">
												<div class="text-2xl font-black" style="color: {m.na ? '#828179' : '#383832'};">{m.na ? 'N/A' : m.tdec ? m.t1.toFixed(m.tdec) + '%' : fmtV(m.t1)}</div>
												<div class="text-[9px] font-bold" style="color: #65655e;">TOTAL</div>
												<div class="text-[8px]" style="color: #9d9d91;">3D: {m.na ? 'N/A' : m.tdec ? m.t3.toFixed(m.tdec) + '%' : fmtV(m.t3)}</div>
											</div>
											{#if !m.noSite}
												<div class="p-3 flex flex-col justify-center" style="flex: 1;">
													<div class="text-2xl font-black" style="color: {m.na ? '#828179' : '#383832'};">{m.na ? 'N/A' : fmtV(m.s1)}</div>
													<div class="text-[9px] font-bold" style="color: #65655e;">{m.sl}</div>
													<div class="text-[8px]" style="color: #9d9d91;">3D: {m.na ? 'N/A' : fmtV(m.s3)}</div>
												</div>
											{/if}
										</div>
										<div class="px-3 py-1 text-[8px] font-mono" style="background: #f6f4e9; color: #9d9d91; border-top: 1px solid #ebe8dd;">{m.tc}</div>
									</div>
								{/each}
							</div>

							<!-- Storyline -->
							{#if periodKpis.story && periodKpis.story.length > 0}
								<div class="px-4 py-3" style="background: white; border-top: 2px solid #383832;">
									<div class="text-[10px] font-black uppercase mb-2" style="color: #383832;">SITUATION REPORT</div>
									<div class="text-xs leading-relaxed" style="color: #383832;">
										{#each periodKpis.story as line}
											<p class="mb-1">{line}</p>
										{/each}
									</div>
								</div>
							{/if}

							<!-- Sector Snapshot (Group view only) -->
							{#if sectorSnap.length > 1}
								<div class="px-4 py-2" style="background: white; border-top: 2px solid #383832;">
									<div class="text-[10px] font-black uppercase mb-2" style="color: #383832;">SECTOR SNAPSHOT</div>
									<div class="overflow-x-auto">
										<table class="w-full text-xs">
											<thead><tr style="background: #ebe8dd;">
												<th class="py-1.5 px-2 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">SECTOR</th>
												<th class="py-1.5 px-2 text-center font-black">SITES</th>
												<th class="py-1.5 px-2 text-center font-black">BUFFER</th>
												<th class="py-1.5 px-2 text-center font-black">BURN</th>
												<th class="py-1.5 px-2 text-center font-black">COST</th>
												<th class="py-1.5 px-2 text-center font-black">BO HR</th>
												<th class="py-1.5 px-2 text-center font-black">DIESEL%</th>
												<th class="py-1.5 px-2 text-center font-black">CRIT</th>
												<th class="py-1.5 px-2 text-center font-black">STATUS</th>
											</tr></thead>
											<tbody>
												{#each sectorSnap as ss, si}
													{@const bfc = ss.buffer >= 7 ? '#007518' : ss.buffer >= 3 ? '#ff9d00' : '#be2d06'}
													<tr style="background: {si % 2 ? '#f6f4e9' : 'white'}; border-bottom: 1px solid #ebe8dd;">
														<td class="py-1.5 px-2 font-bold">{ss.sector}</td>
														<td class="py-1.5 px-2 text-center">{ss.sites}</td>
														<td class="py-1.5 px-2 text-center font-bold" style="color: {bfc};">{ss.buffer}d</td>
														<td class="py-1.5 px-2 text-center font-mono">{fmtV(ss.burn)}</td>
														<td class="py-1.5 px-2 text-center font-mono">{fmtV(ss.cost)}</td>
														<td class="py-1.5 px-2 text-center font-mono">{ss.blackout}</td>
														<td class="py-1.5 px-2 text-center font-mono">{ss.diesel_pct != null ? ss.diesel_pct + '%' : 'N/A'}</td>
														<td class="py-1.5 px-2 text-center font-black" style="color: {ss.crit > 0 ? '#be2d06' : '#65655e'};">{ss.crit}</td>
														<td class="py-1.5 px-2 text-center">{ss.status}</td>
													</tr>
												{/each}
											</tbody>
										</table>
									</div>
								</div>
							{/if}
						</div>
					{/if}
				</div>
				{:else if dashSection === 'trends'}
					<!-- Quick Navigation -->
					{@const storyChapters = [
						{ id: 'ch-blackout', icon: 'power_off', label: '1. BLACKOUTS' },
						{ id: 'ch-fuel', icon: 'local_gas_station', label: '2. FUEL' },
						{ id: 'ch-cost', icon: 'payments', label: '3. COST' },
						{ id: 'ch-revenue', icon: 'trending_down', label: '4. REVENUE' },
						{ id: 'ch-buffer', icon: 'battery_alert', label: '5. BUFFER' },
						{ id: 'ch-efficiency', icon: 'speed', label: '6. WASTE' },
						{ id: 'ch-rolling', icon: 'trending_up', label: '7. TRENDS' },
						{ id: 'ch-monthly', icon: 'calendar_month', label: '8. GRADES' },
					]}
					<div class="flex flex-wrap gap-1 mb-4 p-2 sticky top-28 z-20" style="background: #f6f4e9; border: 2px solid #383832;">
						<span class="text-[9px] font-black uppercase self-center mr-2" style="color: #65655e;">JUMP TO:</span>
						{#each storyChapters as ch}
							<button onclick={() => document.getElementById(ch.id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
								class="px-3 py-1.5 text-[9px] font-black uppercase flex items-center gap-1 transition-colors hover:bg-[#383832] hover:text-[#feffd6]"
								style="background: white; color: #383832; border: 1px solid #383832;">
								<span class="material-symbols-outlined text-xs">{ch.icon}</span>
								{ch.label}
							</button>
						{/each}
					</div>

					<div class="space-y-6">
						<TrendCharts dateFrom={dateFrom} dateTo={dateTo} sector={sectorApiParam()} />
						<RollingCharts dateFrom={dateFrom} dateTo={dateTo} sector={sectorApiParam()} />

						<!-- #94 Monthly Summary -->
						{#if monthlySummary.length > 0}
							<div>
								<div id="ch-monthly" class="scroll-mt-36"></div>
								<div class="flex items-center gap-3 px-4 py-3" style="background: #383832; color: #feffd6;">
									<span class="material-symbols-outlined text-xl" style="color: #00fc40;">calendar_month</span>
									<div>
										<div class="font-black uppercase text-sm">CHAPTER 7: MONTHLY SUMMARY</div>
										<div class="text-[10px] opacity-75">Month-by-month performance grades and trends</div>
									</div>
								</div>
								<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mt-3">
									{#each monthlySummary as m}
										{@const gradeColors: Record<string, string> = { A: '#007518', B: '#006f7c', C: '#ff9d00', D: '#f95630', F: '#be2d06' }}
										{@const gc = gradeColors[m.grade] || '#65655e'}
										<div style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832; background: white;">
											<div class="px-3 py-2 font-black text-sm" style="background: #383832; color: #feffd6;">{m.month}</div>
											<div class="p-3 text-[11px] font-mono space-y-1.5" style="color: #383832;">
												<div class="flex justify-between"><span style="color: #65655e;">Total Fuel</span><span class="font-bold">{m.fuel?.toLocaleString()} L</span></div>
												<div class="flex justify-between"><span style="color: #65655e;">Burn/Day</span><span class="font-bold">{m.burn_per_day?.toLocaleString()} L</span></div>
												<div class="flex justify-between"><span style="color: #65655e;">Blackout</span><span class="font-bold">{m.blackout_hr} hr</span></div>
												<div class="flex justify-between"><span style="color: #65655e;">Buffer</span><span class="font-bold" style="color: {gc};">{m.buffer} days</span></div>
												<div class="flex justify-between"><span style="color: #65655e;">Days</span><span class="font-bold">{m.days}</span></div>
											</div>
											<div class="text-center py-2" style="border-top: 1px solid #ebe8dd;">
												<span class="px-4 py-1 text-sm font-black" style="background: {gc}; color: white;">GRADE: {m.grade}</span>
											</div>
										</div>
									{/each}
								</div>
							</div>
						{/if}

						<!-- #77 Blackout Calendar -->
						{#if blackoutCalendar.length > 0}
							{@const calMonths = [...new Set(blackoutCalendar.map((d: any) => d.date.slice(0, 7)))].sort().reverse().slice(0, 3)}
							<div>
								<div class="px-4 py-2.5 font-black text-sm uppercase" style="background: #383832; color: #feffd6;">BLACKOUT CALENDAR</div>
								<div class="mt-3 flex flex-wrap gap-6">
									{#each calMonths as month}
										{@const mData = blackoutCalendar.filter((d: any) => d.date.startsWith(month))}
										{@const year = parseInt(month.slice(0, 4))}
										{@const mon = parseInt(month.slice(5, 7))}
										{@const firstDow = new Date(year, mon - 1, 1).getDay()}
										{@const daysInMonth = new Date(year, mon, 0).getDate()}
										{@const dayMap = new Map(mData.map((d: any) => [parseInt(d.date.slice(8, 10)), d.avg_bo]))}
										<div>
											<div class="font-black text-sm mb-2" style="color: #383832;">{month}</div>
											<div class="grid gap-[3px]" style="grid-template-columns: repeat(7, 28px);">
												{#each ['M','T','W','T','F','S','S'] as dow}
													<div class="text-center text-[9px] font-bold" style="color: #65655e;">{dow}</div>
												{/each}
												{#each Array(firstDow === 0 ? 6 : firstDow - 1) as _}
													<div></div>
												{/each}
												{#each Array(daysInMonth) as _, i}
													{@const day = i + 1}
													{@const v = dayMap.get(day)}
													{@const bg = v == null ? '#ebe8dd' : v < 4 ? '#007518' : v < 8 ? '#ff9d00' : v < 12 ? '#f95630' : '#be2d06'}
													{@const tc = v == null ? '#65655e' : 'white'}
													<div class="text-center text-[10px] font-bold rounded-sm cursor-default"
														style="background: {bg}; color: {tc}; padding: 3px 0;"
														title="{v != null ? v + 'hr' : 'No data'}">{day}</div>
												{/each}
											</div>
										</div>
									{/each}
								</div>
								<div class="flex gap-3 mt-3 text-[10px] font-bold">
									<span class="px-2 py-0.5" style="background: #007518; color: white;">{'<'}4hr</span>
									<span class="px-2 py-0.5" style="background: #ff9d00; color: white;">4-8hr</span>
									<span class="px-2 py-0.5" style="background: #f95630; color: white;">8-12hr</span>
									<span class="px-2 py-0.5" style="background: #be2d06; color: white;">12hr+</span>
									<span class="px-2 py-0.5" style="background: #ebe8dd; color: #65655e;">No data</span>
								</div>
							</div>
						{/if}
					</div>
				{:else if dashSection === 'sector'}
					<!-- Quick Navigation -->
					{@const whereChapters = [
						{ id: 'where-big', icon: 'apartment', label: '1. BIG PICTURE' },
						{ id: 'where-heatmap', icon: 'map', label: '2. HEATMAP' },
						{ id: 'where-segments', icon: 'pie_chart', label: '3. SEGMENTS' },
						{ id: 'where-sites', icon: 'pin_drop', label: '4. ALL SITES' },
						{ id: 'where-rank', icon: 'leaderboard', label: '5. RANKINGS' },
						{ id: 'where-lng', icon: 'bolt', label: '6. REG vs LNG' },
					]}
					<div class="flex flex-wrap gap-1 mb-4 p-2 sticky top-28 z-20" style="background: #f6f4e9; border: 2px solid #383832;">
						<span class="text-[9px] font-black uppercase self-center mr-2" style="color: #65655e;">JUMP TO:</span>
						{#each whereChapters as ch}
							<button onclick={() => document.getElementById(ch.id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
								class="px-3 py-1.5 text-[9px] font-black uppercase flex items-center gap-1 transition-colors hover:bg-[#383832] hover:text-[#feffd6]"
								style="background: white; color: #383832; border: 1px solid #383832;">
								<span class="material-symbols-outlined text-xs">{ch.icon}</span>
								{ch.label}
							</button>
						{/each}
					</div>

					<div class="space-y-6">
						<!-- CH1: THE BIG PICTURE -->
						<div id="where-big" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3">
									<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">apartment</span>
									<div>
										<div class="font-black uppercase text-sm">CHAPTER 1: THE BIG PICTURE</div>
										<div class="text-[10px] opacity-75">Group and company level summary — how does the whole business look?</div>
									</div>
								</div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">
									? Which company uses the most fuel? Who has the most critical sites?
								</div>
							</div>
						</div>

						<!-- CH2: SECTOR HEATMAP -->
						<div id="where-heatmap" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3">
									<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">map</span>
									<div>
										<div class="font-black uppercase text-sm">CHAPTER 2: SECTOR HEATMAP</div>
										<div class="text-[10px] opacity-75">Color-coded overview — green means healthy, red means danger.</div>
									</div>
								</div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">
									? Which sector has the best buffer? Worst blackout? Highest diesel cost?
								</div>
							</div>
						</div>
						<SectorHeatmap dateFrom={dateFrom} dateTo={dateTo} />

						<!-- CH3: SEGMENTS + CH4: ALL SITES (inside SectorSites component) -->
						<div id="where-segments" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3">
									<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">pie_chart</span>
									<div>
										<div class="font-black uppercase text-sm">CHAPTER 3: SEGMENT DEEP DIVE</div>
										<div class="text-[10px] opacity-75">Within each sector — which business segment performs best/worst?</div>
									</div>
								</div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">
									? Is Ocean better than City Mart? Which segment has highest diesel %?
								</div>
							</div>
						</div>

						<div id="where-sites" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3">
									<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">pin_drop</span>
									<div>
										<div class="font-black uppercase text-sm">CHAPTER 4: EVERY SITE</div>
										<div class="text-[10px] opacity-75">Site-by-site data — search, filter, and find specific locations.</div>
									</div>
								</div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">
									? Which specific site needs fuel? Who has the worst efficiency?
								</div>
							</div>
						</div>
						<SectorSites sector={sectorApiParam()} company={activeCompany} sites={selectedSites} />

						<!-- CH5: RANKINGS -->
						<div id="where-rank" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3">
									<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">leaderboard</span>
									<div>
										<div class="font-black uppercase text-sm">CHAPTER 5: TOP PERFORMERS & WORST OFFENDERS</div>
										<div class="text-[10px] opacity-75">Top 15 sites by diesel cost and diesel % of sales — who needs attention most?</div>
									</div>
								</div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">
									? Which sites spend the most on diesel? Where is diesel eating into revenue?
								</div>
							</div>
						</div>
						<Rankings dateFrom={dateFrom} dateTo={dateTo} sector={sectorApiParam()} />

						<!-- CH6: REGULAR vs LNG -->
						<div id="where-lng" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3">
									<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">bolt</span>
									<div>
										<div class="font-black uppercase text-sm">CHAPTER 6: REGULAR vs LNG</div>
										<div class="text-[10px] opacity-75">Comparing diesel generators vs LNG — which fuel type is more efficient?</div>
									</div>
								</div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">
									? Is LNG cheaper per hour? Do LNG sites have better buffer days?
								</div>
							</div>
						</div>
						<LngComparison dateFrom={dateFrom} dateTo={dateTo} />
					</div>
				<!-- ═══ TAB 04: HOW WE RAN ═══ -->
				{:else if dashSection === 'operations'}
					{@const opsNav = [
						{ id: 'ops-modes', icon: 'toggle_on', label: '1. MODES' },
						{ id: 'ops-delivery', icon: 'local_shipping', label: '2. DELIVERY' },
						{ id: 'ops-fleet', icon: 'build', label: '3. FLEET' },
						{ id: 'ops-patterns', icon: 'date_range', label: '4. PATTERNS' },
						{ id: 'ops-scores', icon: 'assessment', label: '5. SCORES' },
					]}
					<div class="flex flex-wrap gap-1 mb-4 p-2 sticky top-28 z-20" style="background: #f6f4e9; border: 2px solid #383832;">
						<span class="text-[9px] font-black uppercase self-center mr-2" style="color: #65655e;">JUMP TO:</span>
						{#each opsNav as ch}
							<button onclick={() => document.getElementById(ch.id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
								class="px-3 py-1.5 text-[9px] font-black uppercase flex items-center gap-1 transition-colors hover:bg-[#383832] hover:text-[#feffd6]"
								style="background: white; color: #383832; border: 1px solid #383832;">
								<span class="material-symbols-outlined text-xs">{ch.icon}</span> {ch.label}
							</button>
						{/each}
					</div>
					<div class="space-y-6">
						<div id="ops-modes" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3"><span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">toggle_on</span><div><div class="font-black uppercase text-sm">CHAPTER 1: OPERATING MODES</div><div class="text-[10px] opacity-75">Should each site stay OPEN, MONITOR, REDUCE hours, or CLOSE?</div></div></div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Which sites should reduce generator hours? Who should close?</div>
							</div>
						</div>
						<div id="ops-delivery" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3"><span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">local_shipping</span><div><div class="font-black uppercase text-sm">CHAPTER 2: FUEL DELIVERY QUEUE</div><div class="text-[10px] opacity-75">Priority-ordered list of sites that need fuel delivery.</div></div></div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Who needs fuel first? How many liters? By when?</div>
							</div>
						</div>
						<OperatingModes sector={sectorApiParam()} company={activeCompany} />

						<div id="ops-fleet" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3"><span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">build</span><div><div class="font-black uppercase text-sm">CHAPTER 3: FLEET & MAINTENANCE</div><div class="text-[10px] opacity-75">Generator health, fuel transfers, load balancing, and anomaly detection.</div></div></div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Which generators need maintenance? Can we move fuel between sites?</div>
							</div>
						</div>
						<OperationsTables sector={sectorApiParam()} />

						<div id="ops-patterns" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3"><span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">date_range</span><div><div class="font-black uppercase text-sm">CHAPTER 4: WEEKLY PATTERNS</div><div class="text-[10px] opacity-75">Week-over-week comparison and day-of-week patterns.</div></div></div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Is this week better than last? Which day burns the most fuel?</div>
							</div>
						</div>
						<div id="ops-scores" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3"><span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">assessment</span><div><div class="font-black uppercase text-sm">CHAPTER 5: PERFORMANCE SCORES</div><div class="text-[10px] opacity-75">Sector comparison, generator utilization, and waste/theft detection.</div></div></div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Which sector scores best? Any generators running suspiciously high?</div>
							</div>
						</div>
						<GroupExtras dateFrom={dateFrom} dateTo={dateTo} sector={sectorApiParam()} />
					</div>

				<!-- ═══ TAB 05: WHAT'S AT RISK ═══ -->
				{:else if dashSection === 'risk'}
					{@const riskNav = [
						{ id: 'risk-grades', icon: 'shield', label: '1. BCP GRADES' },
						{ id: 'risk-actions', icon: 'checklist', label: '2. ACTIONS' },
						{ id: 'risk-alerts', icon: 'notifications_active', label: '3. ALERTS' },
						{ id: 'risk-stockout', icon: 'hourglass_bottom', label: '4. STOCKOUT' },
					]}
					<div class="flex flex-wrap gap-1 mb-4 p-2 sticky top-28 z-20" style="background: #f6f4e9; border: 2px solid #383832;">
						<span class="text-[9px] font-black uppercase self-center mr-2" style="color: #65655e;">JUMP TO:</span>
						{#each riskNav as ch}
							<button onclick={() => document.getElementById(ch.id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
								class="px-3 py-1.5 text-[9px] font-black uppercase flex items-center gap-1 transition-colors hover:bg-[#383832] hover:text-[#feffd6]"
								style="background: white; color: #383832; border: 1px solid #383832;">
								<span class="material-symbols-outlined text-xs">{ch.icon}</span> {ch.label}
							</button>
						{/each}
					</div>
					<div class="space-y-6">
						<div id="risk-grades" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3"><span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">shield</span><div><div class="font-black uppercase text-sm">CHAPTER 1: BCP RISK GRADES</div><div class="text-[10px] opacity-75">A-F grades based on fuel coverage, generator capacity, and resilience.</div></div></div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? What grade does each site get? How many are failing?</div>
							</div>
						</div>
						<div id="risk-actions" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3"><span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">checklist</span><div><div class="font-black uppercase text-sm">CHAPTER 2: RECOMMENDED ACTIONS</div><div class="text-[10px] opacity-75">Rule-based recommendations — what should we do right now?</div></div></div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? What's the most urgent action? Which sites need immediate help?</div>
							</div>
						</div>
						<div id="risk-alerts" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3"><span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">notifications_active</span><div><div class="font-black uppercase text-sm">CHAPTER 3: ACTIVE ALERTS</div><div class="text-[10px] opacity-75">Live alert feed — critical, warning, and info notifications.</div></div></div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? How many critical alerts? Which sites triggered them?</div>
							</div>
						</div>
						<div id="risk-stockout" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3"><span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">hourglass_bottom</span><div><div class="font-black uppercase text-sm">CHAPTER 4: STOCKOUT FORECAST</div><div class="text-[10px] opacity-75">Which sites will run out of fuel in the next 7 days?</div></div></div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Who will run dry first? What date? How confident are we?</div>
							</div>
						</div>
						<RiskPanel />
					</div>

				<!-- ═══ TAB 06: FUEL & COST ═══ -->
				{:else if dashSection === 'fuel'}
					{@const fuelNav = [
						{ id: 'fuel-buy', icon: 'shopping_cart', label: '1. BUY SIGNAL' },
						{ id: 'fuel-budget', icon: 'account_balance', label: '2. BUDGET' },
						{ id: 'fuel-price', icon: 'show_chart', label: '3. PRICES' },
						{ id: 'fuel-analysis', icon: 'analytics', label: '4. ANALYSIS' },
						{ id: 'fuel-ocean', icon: 'waves', label: '5. OCEAN' },
					]}
					<div class="flex flex-wrap gap-1 mb-4 p-2 sticky top-28 z-20" style="background: #f6f4e9; border: 2px solid #383832;">
						<span class="text-[9px] font-black uppercase self-center mr-2" style="color: #65655e;">JUMP TO:</span>
						{#each fuelNav as ch}
							<button onclick={() => document.getElementById(ch.id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
								class="px-3 py-1.5 text-[9px] font-black uppercase flex items-center gap-1 transition-colors hover:bg-[#383832] hover:text-[#feffd6]"
								style="background: white; color: #383832; border: 1px solid #383832;">
								<span class="material-symbols-outlined text-xs">{ch.icon}</span> {ch.label}
							</button>
						{/each}
					</div>
					<div class="space-y-6">
						<div id="fuel-buy" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3"><span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">shopping_cart</span><div><div class="font-black uppercase text-sm">CHAPTER 1: SHOULD WE BUY FUEL?</div><div class="text-[10px] opacity-75">Supplier signals — is now a good time to purchase?</div></div></div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Which supplier has the best price? BUY now or WAIT?</div>
							</div>
						</div>
						<div id="fuel-budget" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3"><span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">account_balance</span><div><div class="font-black uppercase text-sm">CHAPTER 2: WEEKLY BUDGET</div><div class="text-[10px] opacity-75">How much fuel do we need this week and what will it cost?</div></div></div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Total liters needed? Total cost? Per sector breakdown?</div>
							</div>
						</div>
						<div id="fuel-price" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3"><span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">show_chart</span><div><div class="font-black uppercase text-sm">CHAPTER 3: PRICE TRENDS & FORECAST</div><div class="text-[10px] opacity-75">Are fuel prices going up or down? ML-powered 7-day forecast.</div></div></div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Price trend? Which supplier is cheapest? What's the 7-day forecast?</div>
							</div>
						</div>
						<div id="fuel-analysis" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3"><span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">analytics</span><div><div class="font-black uppercase text-sm">CHAPTER 4: COST ANALYSIS</div><div class="text-[10px] opacity-75">Break-even analysis, site mapping status, and fuel wastage report.</div></div></div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Which sites are above break-even? Where is fuel being wasted?</div>
							</div>
						</div>
						<div id="fuel-ocean" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3"><span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">waves</span><div><div class="font-black uppercase text-sm">CHAPTER 5: OCEAN COST ALLOCATION</div><div class="text-[10px] opacity-75">Ocean store diesel costs split by center contribution percentage.</div></div></div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? How much does Ocean really pay? What's the shopping center split?</div>
							</div>
						</div>
						<FuelIntel />
					</div>

				<!-- ═══ TAB 07: WHAT'S NEXT ═══ -->
				{:else if dashSection === 'predictions'}
					{@const predNav = [
						{ id: 'pred-forecast', icon: 'query_stats', label: '1. FORECASTS' },
						{ id: 'pred-risk', icon: 'warning', label: '2. RISK' },
						{ id: 'pred-actions', icon: 'assignment', label: '3. ACTIONS' },
						{ id: 'pred-whatif', icon: 'science', label: '4. WHAT-IF' },
						{ id: 'pred-transfers', icon: 'swap_horiz', label: '5. TRANSFERS' },
					]}
					<div class="flex flex-wrap gap-1 mb-4 p-2 sticky top-28 z-20" style="background: #f6f4e9; border: 2px solid #383832;">
						<span class="text-[9px] font-black uppercase self-center mr-2" style="color: #65655e;">JUMP TO:</span>
						{#each predNav as ch}
							<button onclick={() => document.getElementById(ch.id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
								class="px-3 py-1.5 text-[9px] font-black uppercase flex items-center gap-1 transition-colors hover:bg-[#383832] hover:text-[#feffd6]"
								style="background: white; color: #383832; border: 1px solid #383832;">
								<span class="material-symbols-outlined text-xs">{ch.icon}</span> {ch.label}
							</button>
						{/each}
					</div>
					<div class="space-y-6">
						<div id="pred-forecast" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3"><span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">query_stats</span><div><div class="font-black uppercase text-sm">CHAPTER 1: 7-DAY FORECASTS</div><div class="text-[10px] opacity-75">ML-powered predictions — where are fuel, buffer, cost, and blackout headed?</div></div></div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Will buffer improve or drop? Will costs rise? Is a blackout spike coming?</div>
							</div>
						</div>
						<div id="pred-risk" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3"><span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">warning</span><div><div class="font-black uppercase text-sm">CHAPTER 2: RISK PREDICTIONS</div><div class="text-[10px] opacity-75">At-risk generators, operating mode predictions, waste/theft detection.</div></div></div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Which generators might fail? Which sites should close? Any theft suspected?</div>
							</div>
						</div>
						<div id="pred-actions" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3"><span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">assignment</span><div><div class="font-black uppercase text-sm">CHAPTER 3: ACTION PLAN</div><div class="text-[10px] opacity-75">Delivery schedule, sites to close, weekly budget forecast.</div></div></div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? What fuel to deliver where? Which sites to shut down? Weekly budget?</div>
							</div>
						</div>
						<Predictions sector={sectorApiParam()} dateFrom={dateFrom} dateTo={dateTo} />

						<div id="pred-whatif" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3"><span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">science</span><div><div class="font-black uppercase text-sm">CHAPTER 4: WHAT-IF SIMULATOR</div><div class="text-[10px] opacity-75">What happens if fuel price changes? If consumption drops? Scenario planning.</div></div></div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? What if price rises 20%? What if we cut generator hours by 30%?</div>
							</div>
						</div>
						<WhatIf />

						<div id="pred-transfers" class="scroll-mt-36">
							<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
								<div class="flex items-center gap-3"><span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">swap_horiz</span><div><div class="font-black uppercase text-sm">CHAPTER 5: FUEL TRANSFERS</div><div class="text-[10px] opacity-75">Can we move fuel from surplus sites to deficit sites?</div></div></div>
								<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">? Which sites have excess fuel? Who can share? How many liters to transfer?</div>
							</div>
						</div>
						{#if transferData.length > 0}
							<div style="border: 2px solid #383832; background: white;">
								<div class="px-4 py-2 flex justify-between items-center" style="background: #383832; color: #feffd6;">
									<span class="font-bold uppercase text-sm">RECOMMENDED FUEL TRANSFERS</span>
									<span class="text-[10px]">{transferData.length} opportunities</span>
								</div>
								<div class="overflow-x-auto">
									<table class="w-full text-xs">
										<thead><tr style="background: #ebe8dd;">
											<th class="py-2 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">From</th>
											<th class="py-2 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">To</th>
											<th class="py-2 px-3 text-center font-black uppercase" style="border-bottom: 2px solid #383832;">Liters</th>
											<th class="py-2 px-3 text-center font-black uppercase" style="border-bottom: 2px solid #383832;">From Buffer</th>
											<th class="py-2 px-3 text-center font-black uppercase" style="border-bottom: 2px solid #383832;">To Buffer</th>
											<th class="py-2 px-3 text-center font-black uppercase" style="border-bottom: 2px solid #383832;">Priority</th>
										</tr></thead>
										<tbody>
											{#each transferData.slice(0, 20) as t, i}
												<tr style="background: {i % 2 ? '#f6f4e9' : 'white'}; border-bottom: 1px solid #ebe8dd;">
													<td class="py-2 px-3 font-bold" style="color: #007518;">{t.from_site || t.donor || '—'}</td>
													<td class="py-2 px-3 font-bold" style="color: #be2d06;">{t.to_site || t.recipient || '—'}</td>
													<td class="py-2 px-3 text-center font-mono">{Math.round(t.liters || t.transfer_liters || 0).toLocaleString()}</td>
													<td class="py-2 px-3 text-center font-mono">{(t.from_buffer || t.donor_buffer || 0).toFixed?.(1) ?? '—'}d</td>
													<td class="py-2 px-3 text-center font-mono">{(t.to_buffer || t.recipient_buffer || 0).toFixed?.(1) ?? '—'}d</td>
													<td class="py-2 px-3 text-center">
														<span class="px-2 py-0.5 text-[10px] font-black uppercase"
															style="background: {(t.priority || t.urgency || 'MEDIUM') === 'HIGH' || (t.priority || t.urgency || 'MEDIUM') === 'CRITICAL' ? '#be2d06' : (t.priority || t.urgency || 'MEDIUM') === 'MEDIUM' ? '#ff9d00' : '#007518'}; color: white;">{t.priority || t.urgency || 'MEDIUM'}</span>
													</td>
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
							</div>
						{/if}
					</div>
				{:else if dashSection === 'ai'}
					<AiInsights kpiData={k} heatmapData={heatmapRows} />
				{/if}
			</div>
		</div>

		<!-- Site Modal -->
		{#if showSiteModal}
			<SiteModal siteId={modalSiteId} {sites} onclose={() => showSiteModal = false} />
		{/if}

		<!-- Site Comparison Modal -->
		{#if showComparison && selectedSites.length === 2}
			<div class="fixed inset-0 z-[200] flex items-center justify-center" style="background: rgba(0,0,0,0.6);"
				onclick={() => showComparison = false}>
				<div class="w-[90vw] max-w-[800px] max-h-[80vh] overflow-y-auto"
					style="background: #feffd6; border: 3px solid #383832; box-shadow: 6px 6px 0px 0px #383832;"
					onclick={(e) => e.stopPropagation()}>

					<div class="px-4 py-3 flex justify-between items-center" style="background: #383832; color: #feffd6;">
						<span class="font-black uppercase text-sm">SITE COMPARISON</span>
						<button onclick={() => showComparison = false} class="font-black text-lg">&#10005;</button>
					</div>

					<div class="overflow-x-auto">
						<table class="w-full text-xs">
							<thead><tr style="background: #ebe8dd;">
								<th class="py-2 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">METRIC</th>
								<th class="py-2 px-3 text-center font-black uppercase" style="border-bottom: 2px solid #383832; color: #006f7c;">{selectedSites[0]}</th>
								<th class="py-2 px-3 text-center font-black uppercase" style="border-bottom: 2px solid #383832; color: #9d4867;">{selectedSites[1]}</th>
								<th class="py-2 px-3 text-center font-black uppercase" style="border-bottom: 2px solid #383832;">WINNER</th>
							</tr></thead>
							<tbody>
								{#each compareData() as m, i}
									{@const better1 = m.higher ? (m.v1 || 0) > (m.v2 || 0) : (m.v1 || 0) < (m.v2 || 0)}
									{@const better2 = !better1 && (m.v1 || 0) !== (m.v2 || 0)}
									<tr style="background: {i % 2 ? '#f6f4e9' : 'white'}; border-bottom: 1px solid #ebe8dd;">
										<td class="py-2 px-3 font-bold" style="color: #383832;">{m.name}</td>
										<td class="py-2 px-3 text-center font-mono" style="color: {better1 ? '#007518' : '#383832'}; font-weight: {better1 ? '800' : '400'};">
											{typeof m.v1 === 'number' ? m.v1.toLocaleString(undefined, {maximumFractionDigits: 1}) : '\u2014'}
										</td>
										<td class="py-2 px-3 text-center font-mono" style="color: {better2 ? '#007518' : '#383832'}; font-weight: {better2 ? '800' : '400'};">
											{typeof m.v2 === 'number' ? m.v2.toLocaleString(undefined, {maximumFractionDigits: 1}) : '\u2014'}
										</td>
										<td class="py-2 px-3 text-center font-black text-[10px]" style="color: {better1 ? '#006f7c' : better2 ? '#9d4867' : '#65655e'};">
											{better1 ? selectedSites[0].split('-').pop() : better2 ? selectedSites[1].split('-').pop() : 'TIE'}
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</div>
			</div>
		{/if}
	{:else}
		<div class="text-center py-16" style="background: #f6f4e9; border: 2px solid #383832;">
			<span class="material-symbols-outlined text-5xl" style="color: #65655e;">inbox</span>
			<p class="font-bold mt-3 uppercase text-sm" style="color: #383832;">NO DATA FOR SELECTED FILTERS</p>
			<p class="text-xs mt-2" style="color: #65655e;">Try selecting a different sector, date range, or upload data first.</p>
		</div>
	{/if}
{/if}
