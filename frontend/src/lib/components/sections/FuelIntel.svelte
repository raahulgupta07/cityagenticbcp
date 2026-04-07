<script lang="ts">
	import { api, downloadExcel } from '$lib/api';
	import { onMount } from 'svelte';
	import Chart from '$lib/components/Chart.svelte';
	import { lineChart, hbarChart } from '$lib/charts';

	let buySignal: any = $state({});
	let budget: any = $state({});
	let forecast: any = $state({});
	let purchaseLog: any[] = $state([]);
	let mapped: any[] = $state([]);
	let unmapped: any[] = $state([]);
	let mappedCount = $state(0);
	let unmappedCount = $state(0);
	let breakEven: any[] = $state([]);
	let anomalies: any[] = $state([]);
	let oceanAlloc: any = $state({ stores: [], total_center_cost: 0, total_ocean_share: 0 });
	let loading = $state(true);
	let error = $state('');

	async function load() {
		loading = true;
		error = '';
		try {
			const data = await api.get('/fuel-intel');
			buySignal = data.buy_signal || {};
			budget = data.weekly_budget || {};
			forecast = data.forecast || {};
			purchaseLog = data.purchase_log || [];
		} catch (e) {
			console.error(e);
			error = 'Failed to load fuel intelligence data. Check your connection and try again.';
			loading = false;
			return;
		}
		try {
			const [sm, be, an, oa] = await Promise.all([
				api.get('/site-mapping'),
				api.get('/break-even'),
				api.get('/anomalies').catch(() => ({ sites: [] })),
				api.get('/ocean-cost-allocation').catch(() => ({ stores: [] })),
			]);
			oceanAlloc = oa;
			mapped = sm.mapped || [];
			unmapped = sm.unmapped || [];
			mappedCount = sm.mapped_count || 0;
			unmappedCount = sm.unmapped_count || 0;
			breakEven = be.sites || [];
			anomalies = an.sites || an || [];
		} catch {}
		loading = false;
	}

	onMount(load);

	/* ---------- derived: forecast chart option ---------- */
	let chartOption = $derived.by(() => {
		if (!forecast.history && !forecast.forecast) return null;

		const series: { name: string; data: number[]; color: string }[] = [];
		let categories: string[] = [];

		if (forecast.history) {
			const dates = forecast.history.map((h: any) => h.date);
			const prices = forecast.history.map((h: any) => h.price);
			categories = [...dates];
			series.push({ name: 'HISTORY', data: prices, color: '#383832' });
		}

		if (forecast.forecast) {
			const fDates = forecast.forecast.map((f: any) => f.date);
			const fPrices = forecast.forecast.map((f: any) => f.predicted_price);
			/* pad forecast data so it starts after history */
			const padLen = categories.length;
			const padded = Array(padLen).fill(null as any).concat(fPrices);
			categories = [...categories, ...fDates];
			series.push({ name: 'FORECAST', data: padded, color: '#006f7c' });
		}

		const subtitle = [
			forecast.r2 != null ? `R\u00b2: ${Number(forecast.r2).toFixed(3)}` : '',
			forecast.trend ? `TREND: ${forecast.trend}` : ''
		].filter(Boolean).join('  |  ');

		const opt = lineChart(categories, series, { title: 'FUEL_PRICE_FORECAST' });
		if (subtitle) {
			(opt as any).title.subtext = subtitle;
			(opt as any).title.subtextStyle = { color: '#65655e', fontWeight: 700, fontSize: 11, fontFamily: 'Space Grotesk, monospace' };
		}
		/* make forecast line dashed */
		if ((opt as any).series.length > 1) {
			(opt as any).series[1].lineStyle = { color: '#006f7c', type: 'dashed' };
		}
		return opt;
	});

	/* ---------- derived: budget total ---------- */
	let budgetRows = $derived(budget.rows || []);
	let budgetTotal = $derived(
		budgetRows.reduce((s: number, r: any) => s + (r.weekly_cost || 0), 0)
	);

	/* ---------- helpers ---------- */
	function badgeColor(rec: string): string {
		const r = (rec || '').toUpperCase();
		if (r === 'BUY_NOW') return '#007518';
		if (r === 'WAIT') return '#ff9d00';
		if (r === 'AVOID') return '#be2d06';
		return '#383832';
	}

	function trendArrow(trend: string): string {
		const t = (trend || '').toLowerCase();
		if (t === 'up' || t === 'rising') return '\u2191';
		if (t === 'down' || t === 'falling') return '\u2193';
		return '\u2192';
	}

	function fmtNum(v: number | null | undefined, decimals = 2): string {
		if (v == null) return '-';
		return Number(v).toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
	}

	let suppliers = $derived(buySignal.suppliers || []);
	let cheapest = $derived(buySignal.cheapest || '');
	let savingsPct = $derived(buySignal.savings_pct ?? null);

	function beColor(rec: string): string {
		const r = (rec || '').toUpperCase();
		if (r === 'OPEN') return '#007518';
		if (r === 'MONITOR') return '#006f7c';
		if (r === 'REDUCE') return '#ff9d00';
		if (r === 'CLOSE') return '#be2d06';
		return '#383832';
	}

	let search = $state('');
	const matchSearch = (r: any) => Object.values(r).some(v => String(v).toLowerCase().includes(search.toLowerCase()));
	const filteredBreakEven = $derived(search ? breakEven.filter(matchSearch) : breakEven);
	const filteredMapped = $derived(search ? mapped.filter(matchSearch) : mapped);
	const filteredUnmapped = $derived(search ? unmapped.filter(matchSearch) : unmapped);
	const filteredPurchaseLog = $derived(search ? purchaseLog.filter(matchSearch) : purchaseLog);
	let recentLog = $derived(filteredPurchaseLog.slice(0, 50));

	/* ---------- #72 Daily Price Trend by Supplier ---------- */
	let priceTrendOption = $derived.by(() => {
		if (!purchaseLog.length) return null;
		const grouped: Record<string, Record<string, number[]>> = {};
		for (const r of purchaseLog) {
			const d = r.date || '';
			const s = r.supplier || 'UNKNOWN';
			if (!grouped[d]) grouped[d] = {};
			if (!grouped[d][s]) grouped[d][s] = [];
			grouped[d][s].push(r.price_per_l ?? r.price_per_liter ?? 0);
		}
		const dates = Object.keys(grouped).sort();
		const suppliers = [...new Set(purchaseLog.map((r: any) => r.supplier || 'UNKNOWN'))];
		const colors = ['#007518', '#006f7c', '#be2d06', '#ff9d00', '#383832', '#9C27B0'];
		const series = suppliers.map((sup, i) => ({
			name: sup,
			data: dates.map(d => {
				const vals = grouped[d]?.[sup];
				return vals ? vals.reduce((a: number, b: number) => a + b, 0) / vals.length : (null as any);
			}),
			color: colors[i % colors.length]
		}));
		return lineChart(dates, series, { title: 'DAILY PRICE TREND BY SUPPLIER' });
	});

	/* ---------- #73 Purchase Volume by Supplier ---------- */
	let volumeBySupplier = $derived.by(() => {
		if (!purchaseLog.length) return null;
		const sums: Record<string, number> = {};
		for (const r of purchaseLog) {
			const s = r.supplier || 'UNKNOWN';
			sums[s] = (sums[s] || 0) + (r.qty_l ?? r.quantity_liters ?? 0);
		}
		const entries = Object.entries(sums).sort((a, b) => b[1] - a[1]);
		const cats = entries.map(e => e[0]);
		const vals = entries.map(e => e[1]);
		const colors = vals.map(() => '#006f7c');
		return hbarChart(cats, vals, { title: 'PURCHASE VOLUME BY SUPPLIER (L)', colors });
	});

	/* ---------- #74 Fuel Wastage Report ---------- */
	let wasteSites = $derived(
		(Array.isArray(anomalies) ? anomalies : []).filter((s: any) => (s.waste_score ?? s.waste_pct ?? 0) > 15)
	);

	let sortedBreakEven = $derived(
		[...filteredBreakEven].sort((a, b) => (b.diesel_pct ?? 0) - (a.diesel_pct ?? 0))
	);
	let closeCount = $derived(
		breakEven.filter((s) => (s.recommendation || '').toUpperCase() === 'CLOSE').length
	);
</script>

{#if loading}
	<div class="flex items-center justify-center py-16">
		<span class="text-sm font-black uppercase animate-pulse" style="color:#383832;">LOADING FUEL INTEL...</span>
	</div>
{:else if error}
	<div class="text-center py-12" style="background: #f6f4e9; border: 2px solid #383832;">
		<span class="material-symbols-outlined text-3xl" style="color: #be2d06;">error</span>
		<p class="font-bold mt-2 uppercase text-xs" style="color: #be2d06;">{error}</p>
		<button onclick={load} class="mt-3 px-4 py-1.5 text-[10px] font-black uppercase"
			style="background: #383832; color: #feffd6; border: 2px solid #383832;">
			<span class="material-symbols-outlined text-xs align-middle">refresh</span> RETRY
		</button>
	</div>
{:else if suppliers.length === 0 && budgetRows.length === 0 && purchaseLog.length === 0 && breakEven.length === 0}
	<div class="text-center py-12" style="background: #f6f4e9; border: 2px solid #383832;">
		<span class="material-symbols-outlined text-3xl" style="color: #65655e;">inbox</span>
		<p class="font-bold mt-2 uppercase text-xs" style="color: #383832;">NO DATA AVAILABLE</p>
		<p class="text-[10px] mt-1" style="color: #65655e;">Upload data or adjust your filters.</p>
	</div>
{:else}

<div class="px-3 py-2 flex items-center gap-2 mb-4" style="background: #ebe8dd; border: 2px solid #383832;">
	<span class="material-symbols-outlined text-sm" style="color: #65655e;">search</span>
	<input type="text" bind:value={search} placeholder="QUICK_SEARCH..."
		class="flex-1 px-2 py-1 text-xs font-mono uppercase"
		style="background: white; border: 1px solid #383832; color: #383832;" />
</div>

<!-- ============ SECTION 1: SUPPLIER BUY SIGNAL ============ -->
<div class="mb-8">
	<div class="px-4 py-2 mb-4" style="background:#383832;border:2px solid #383832;">
		<h2 class="text-sm font-black uppercase tracking-wider" style="color:#feffd6;">
			SUPPLIER_BUY_SIGNAL
			{#if cheapest}
				<span class="ml-4 text-xs" style="color:#007518;">CHEAPEST: {cheapest}</span>
			{/if}
			{#if savingsPct != null}
				<span class="ml-2 text-xs" style="color:#ff9d00;">SAVE {fmtNum(savingsPct, 1)}%</span>
			{/if}
		</h2>
	</div>

	{#if suppliers.length > 0}
		<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
			{#each suppliers as sup}
				<div
					class="p-4 relative"
					style="background:#feffd6;border:2px solid #383832;box-shadow:4px 4px 0px 0px #383832;"
					class:ring-2={sup.name === cheapest}
					style:ring-color={sup.name === cheapest ? '#007518' : 'transparent'}
				>
					{#if sup.name === cheapest}
						<div class="absolute top-0 right-0 px-2 py-0.5 text-[9px] font-black uppercase" style="background:#007518;color:#feffd6;">
							CHEAPEST
						</div>
					{/if}

					<div class="text-xs font-black uppercase mb-2" style="color:#383832;">{sup.name || 'UNKNOWN'}</div>

					<div class="flex items-baseline gap-2 mb-1">
						<span class="text-lg font-black" style="color:#383832;">{fmtNum(sup.current_price)}</span>
						<span class="text-xs" style="color:#65655e;">MMK/L</span>
						<span class="text-base" style="color:{sup.trend === 'up' || sup.trend === 'rising' ? '#be2d06' : sup.trend === 'down' || sup.trend === 'falling' ? '#007518' : '#383832'};">
							{trendArrow(sup.trend)}
						</span>
					</div>

					<div class="text-[10px] mb-3" style="color:#65655e;">
						AVG: {fmtNum(sup.avg_price)} MMK/L
					</div>

					<span
						class="inline-block px-3 py-1 text-[10px] font-black uppercase"
						style="background:{badgeColor(sup.recommendation)};color:#feffd6;border:1px solid #383832;"
					>
						{sup.recommendation || 'N/A'}
					</span>
				</div>
			{/each}
		</div>
	{:else}
		<p class="text-xs" style="color:#65655e;">No supplier data available.</p>
	{/if}
</div>

<!-- ============ SECTION 2: WEEKLY BUDGET BREAKDOWN ============ -->
<div class="mb-8">
	<div class="px-4 py-2 mb-4 flex items-center justify-between" style="background:#383832;border:2px solid #383832;">
		<h2 class="text-sm font-black uppercase tracking-wider" style="color:#feffd6;">WEEKLY_BUDGET_FORECAST</h2>
		<div class="flex items-center gap-3">
			{#if budget.total_weekly_cost != null}
				<span class="text-sm font-black" style="color:#ff9d00;">{fmtNum(budget.total_weekly_cost, 0)} MMK</span>
			{/if}
			<button onclick={() => downloadExcel(budgetRows, 'Weekly Budget')}
				class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
				style="color: #00fc40;">
				<span class="material-symbols-outlined text-sm">download</span> EXCEL
			</button>
		</div>
	</div>

	{#if budgetRows.length > 0}
		<div class="overflow-x-auto" style="border:2px solid #383832;">
			<table class="w-full text-xs" style="background:#feffd6;">
				<thead>
					<tr style="background:#383832;">
						<th class="px-3 py-2 text-left font-black uppercase tracking-wider" style="color:#feffd6;">SECTOR</th>
						<th class="px-3 py-2 text-right font-black uppercase tracking-wider" style="color:#feffd6;">AVG_DAILY_L</th>
						<th class="px-3 py-2 text-right font-black uppercase tracking-wider" style="color:#feffd6;">WEEKLY_L</th>
						<th class="px-3 py-2 text-right font-black uppercase tracking-wider" style="color:#feffd6;">PRICE/L</th>
						<th class="px-3 py-2 text-right font-black uppercase tracking-wider" style="color:#feffd6;">WEEKLY_COST</th>
					</tr>
				</thead>
				<tbody>
					{#each budgetRows as row, i}
						<tr style="background:{i % 2 === 0 ? '#feffd6' : '#f6f4e0'};border-top:1px solid #383832;">
							<td class="px-3 py-2 font-bold uppercase" style="color:#383832;">{row.sector || '-'}</td>
							<td class="px-3 py-2 text-right" style="color:#383832;">{fmtNum(row.avg_daily_l, 1)}</td>
							<td class="px-3 py-2 text-right" style="color:#383832;">{fmtNum(row.weekly_l, 1)}</td>
							<td class="px-3 py-2 text-right" style="color:#383832;">{fmtNum(row.price_per_l)}</td>
							<td class="px-3 py-2 text-right font-bold" style="color:#383832;">{fmtNum(row.weekly_cost, 0)}</td>
						</tr>
					{/each}
				</tbody>
				<tfoot>
					<tr style="background:#383832;border-top:2px solid #383832;">
						<td class="px-3 py-2 font-black uppercase" style="color:#feffd6;">TOTAL</td>
						<td class="px-3 py-2" style="color:#feffd6;"></td>
						<td class="px-3 py-2" style="color:#feffd6;"></td>
						<td class="px-3 py-2" style="color:#feffd6;"></td>
						<td class="px-3 py-2 text-right font-black text-base" style="color:#ff9d00;">{fmtNum(budgetTotal, 0)} MMK</td>
					</tr>
				</tfoot>
			</table>
		</div>
	{:else}
		<p class="text-xs" style="color:#65655e;">No budget data available.</p>
	{/if}
</div>

<!-- ============ SECTION 3: FUEL PRICE FORECAST CHART ============ -->
<div class="mb-8">
	<div class="px-4 py-2 mb-4" style="background:#383832;border:2px solid #383832;">
		<h2 class="text-sm font-black uppercase tracking-wider" style="color:#feffd6;">FUEL_PRICE_FORECAST</h2>
	</div>

	{#if forecast.error}
		<div class="p-4 text-xs font-bold" style="background:#feffd6;border:2px solid #be2d06;color:#be2d06;">
			{forecast.error}
		</div>
	{:else if chartOption}
		<Chart option={chartOption} height="400px" guide={{ formula: "Ridge regression model predicts next 7 days of fuel prices using day, day_of_week, lag, and rolling mean features.", sources: [{ data: 'Fuel Price', file: 'fuel_purchases table', col: 'price_per_l', method: 'Ridge regression' }], reading: [{ color: 'blue', text: 'Dark line = Actual historical prices' }, { color: 'green', text: 'Dashed line = ML forecast (7-day)' }, { color: 'amber', text: 'R-squared closer to 1.0 = More reliable' }], explain: "Uses <b>machine learning</b> to predict diesel prices. The dashed line shows where prices are heading. R-squared measures prediction quality." }} />
	{:else}
		<p class="text-xs" style="color:#65655e;">No forecast data available.</p>
	{/if}
</div>

<!-- ============ SECTION 4: PURCHASE LOG ============ -->
<div class="mb-8">
	<div class="px-4 py-2 mb-4 flex items-center justify-between" style="background:#383832;border:2px solid #383832;">
		<h2 class="text-sm font-black uppercase tracking-wider" style="color:#feffd6;">PURCHASE_LOG &mdash; RECENT</h2>
		<button onclick={() => downloadExcel(purchaseLog, 'Purchase Log')}
			class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
			style="color: #00fc40;">
			<span class="material-symbols-outlined text-sm">download</span> EXCEL
		</button>
	</div>

	{#if recentLog.length > 0}
		<div class="overflow-x-auto" style="border:2px solid #383832;">
			<table class="w-full text-xs" style="background:#feffd6;">
				<thead>
					<tr style="background:#383832;">
						<th class="px-3 py-2 text-left font-black uppercase tracking-wider" style="color:#feffd6;">DATE</th>
						<th class="px-3 py-2 text-left font-black uppercase tracking-wider" style="color:#feffd6;">SECTOR</th>
						<th class="px-3 py-2 text-left font-black uppercase tracking-wider" style="color:#feffd6;">SUPPLIER</th>
						<th class="px-3 py-2 text-left font-black uppercase tracking-wider" style="color:#feffd6;">TYPE</th>
						<th class="px-3 py-2 text-right font-black uppercase tracking-wider" style="color:#feffd6;">QTY_L</th>
						<th class="px-3 py-2 text-right font-black uppercase tracking-wider" style="color:#feffd6;">PRICE/L</th>
					</tr>
				</thead>
				<tbody>
					{#each recentLog as row, i}
						<tr style="background:{i % 2 === 0 ? '#feffd6' : '#f6f4e0'};border-top:1px solid #383832;">
							<td class="px-3 py-2 font-mono" style="color:#383832;">{row.date || '-'}</td>
							<td class="px-3 py-2 uppercase" style="color:#383832;">{row.sector || '-'}</td>
							<td class="px-3 py-2" style="color:#383832;">{row.supplier || '-'}</td>
							<td class="px-3 py-2 uppercase" style="color:#383832;">{row.type || '-'}</td>
							<td class="px-3 py-2 text-right" style="color:#383832;">{fmtNum(row.qty_l, 1)}</td>
							<td class="px-3 py-2 text-right" style="color:#383832;">{fmtNum(row.price_per_l)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{:else}
		<p class="text-xs" style="color:#65655e;">No purchase records available.</p>
	{/if}
</div>

<!-- ============ SECTION 4b: PRICE ANALYSIS ============ -->
<div style="background: #383832; color: #feffd6;" class="px-4 py-2.5 font-black text-sm uppercase mt-6">PRICE ANALYSIS</div>

<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4 mb-6">
	<!-- #72 Daily Price Trend by Supplier -->
	{#if priceTrendOption}
		<Chart option={priceTrendOption} height="360px" guide={{ formula: 'Average price_per_liter per date per supplier, plotted as multi-line chart.', sources: [{ data: 'Purchase Log', file: 'fuel_purchases table', col: 'price_per_l', method: 'AVG per date+supplier' }], reading: [{ color: 'green', text: 'Falling line = Prices dropping — good time to buy' }, { color: 'red', text: 'Rising line = Prices increasing — lock in current rate' }, { color: 'amber', text: 'Diverging lines = Supplier price gap widening' }], explain: 'Tracks <b>daily diesel prices</b> for each supplier. Compare lines to find who offers the best rate over time.' }} />
	{/if}

	<!-- #73 Purchase Volume by Supplier -->
	{#if volumeBySupplier}
		<Chart option={volumeBySupplier} height="{Math.max(200, (Object.keys(volumeBySupplier.yAxis?.data || []).length || 4) * 36)}px" guide={{ formula: 'SUM of quantity_liters grouped by supplier.', sources: [{ data: 'Purchase Log', file: 'fuel_purchases table', col: 'qty_l', method: 'SUM per supplier' }], reading: [{ color: 'green', text: 'Longest bar = Primary supplier by volume' }, { color: 'amber', text: 'Short bars = Backup or occasional suppliers' }], explain: 'Shows <b>total liters purchased</b> from each supplier. Helps negotiate better rates with your biggest vendor.' }} />
	{/if}
</div>

<!-- #74 Fuel Wastage Report -->
{#if wasteSites.length > 0}
	<div class="mb-8">
		<div class="px-4 py-2 mb-4 flex items-center justify-between" style="background:#383832;border:2px solid #383832;">
			<h2 class="text-sm font-black uppercase tracking-wider" style="color:#feffd6;">FUEL WASTAGE REPORT</h2>
			<div class="flex items-center gap-3">
				<span class="px-2 py-0.5 text-[10px] font-black" style="background:#be2d06;color:#feffd6;">{wasteSites.length} SITES</span>
				<button onclick={() => downloadExcel(wasteSites, 'Fuel Wastage')}
					class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
					style="color: #00fc40;">
					<span class="material-symbols-outlined text-sm">download</span> EXCEL
				</button>
			</div>
		</div>
		<div class="overflow-x-auto" style="border:2px solid #383832;">
			<table class="w-full text-xs" style="background:#feffd6;">
				<thead>
					<tr style="background:#383832;">
						<th class="px-3 py-2 text-left font-black uppercase tracking-wider" style="color:#feffd6;">SITE</th>
						<th class="px-3 py-2 text-right font-black uppercase tracking-wider" style="color:#feffd6;">ACTUAL L/HR</th>
						<th class="px-3 py-2 text-right font-black uppercase tracking-wider" style="color:#feffd6;">EXPECTED L/HR</th>
						<th class="px-3 py-2 text-right font-black uppercase tracking-wider" style="color:#feffd6;">WASTE %</th>
						<th class="px-3 py-2 text-center font-black uppercase tracking-wider" style="color:#feffd6;">WASTE STATUS</th>
					</tr>
				</thead>
				<tbody>
					{#each wasteSites as row, i}
						{@const wpct = row.waste_score ?? row.waste_pct ?? 0}
						<tr style="background:{wpct > 30 ? '#fde8e4' : i % 2 === 0 ? '#feffd6' : '#f6f4e0'};border-top:1px solid #383832;">
							<td class="px-3 py-2 font-bold uppercase" style="color:#383832;">{row.site_id || '-'}</td>
							<td class="px-3 py-2 text-right" style="color:#383832;">{fmtNum(row.actual_l_hr ?? row.avg_l_hr, 2)}</td>
							<td class="px-3 py-2 text-right" style="color:#383832;">{fmtNum(row.expected_l_hr ?? row.rated_l_hr, 2)}</td>
							<td class="px-3 py-2 text-right font-bold" style="color:{wpct > 30 ? '#be2d06' : '#ff9d00'};">{fmtNum(wpct, 1)}%</td>
							<td class="px-3 py-2 text-center">
								<span
									class="inline-block px-3 py-1 text-[10px] font-black uppercase"
									style="background:{wpct > 30 ? '#be2d06' : '#ff9d00'};color:#feffd6;border:1px solid #383832;"
								>
									{wpct > 30 ? 'CRITICAL' : 'INVESTIGATE'}
								</span>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</div>
{/if}

<!-- ============ SECTION 5: BREAK-EVEN ANALYSIS ============ -->
<div class="mb-8">
	<div class="px-4 py-2 mb-4 flex items-center justify-between" style="background:#383832;border:2px solid #383832;">
		<h2 class="text-sm font-black uppercase tracking-wider" style="color:#feffd6;">BREAK_EVEN_ANALYSIS</h2>
		<div class="flex items-center gap-3">
			{#if closeCount > 0}
				<span class="px-2 py-0.5 text-[10px] font-black uppercase" style="background:#be2d06;color:#feffd6;">{closeCount} CLOSE</span>
			{/if}
			<button onclick={() => downloadExcel(sortedBreakEven, 'Break-Even Analysis', { statusColumns: ['recommendation'] })}
				class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
				style="color: #00fc40;">
				<span class="material-symbols-outlined text-sm">download</span> EXCEL
			</button>
		</div>
	</div>

	{#if sortedBreakEven.length > 0}
		<div class="overflow-x-auto" style="border:2px solid #383832;">
			<table class="w-full text-xs" style="background:#feffd6;">
				<thead>
					<tr style="background:#ebe8dd;">
						<th class="px-3 py-2 text-left font-black uppercase tracking-wider" style="color:#383832;border-bottom:2px solid #383832;">SITE_ID</th>
						<th class="px-3 py-2 text-left font-black uppercase tracking-wider" style="color:#383832;border-bottom:2px solid #383832;">SITE_CODE</th>
						<th class="px-3 py-2 text-left font-black uppercase tracking-wider" style="color:#383832;border-bottom:2px solid #383832;">SEGMENT</th>
						<th class="px-3 py-2 text-left font-black uppercase tracking-wider" style="color:#383832;border-bottom:2px solid #383832;">SECTOR</th>
						<th class="px-3 py-2 text-right font-black uppercase tracking-wider" style="color:#383832;border-bottom:2px solid #383832;">AVG_FUEL_L</th>
						<th class="px-3 py-2 text-right font-black uppercase tracking-wider" style="color:#383832;border-bottom:2px solid #383832;">AVG_SALES</th>
						<th class="px-3 py-2 text-right font-black uppercase tracking-wider" style="color:#383832;border-bottom:2px solid #383832;">DAILY_COST</th>
						<th class="px-3 py-2 text-right font-black uppercase tracking-wider" style="color:#383832;border-bottom:2px solid #383832;">DIESEL_%</th>
						<th class="px-3 py-2 text-center font-black uppercase tracking-wider" style="color:#383832;border-bottom:2px solid #383832;">RECOMMENDATION</th>
					</tr>
				</thead>
				<tbody>
					{#each sortedBreakEven as row, i}
						<tr style="background:{(row.recommendation || '').toUpperCase() === 'CLOSE' ? '#fde8e4' : i % 2 === 0 ? '#feffd6' : '#f6f4e0'};border-top:1px solid #383832;">
							<td class="px-3 py-2 font-bold uppercase" style="color:#383832;">{row.site_id || '-'}</td>
							<td class="px-3 py-2 font-mono text-xs" style="color:#383832;">{row.site_code || row.region || ''}</td>
							<td class="px-3 py-2 text-xs" style="color:#383832;">{row.segment_name || ''}</td>
							<td class="px-3 py-2 uppercase" style="color:#383832;">{row.sector || '-'}</td>
							<td class="px-3 py-2 text-right" style="color:#383832;">{fmtNum(row.avg_fuel_l, 1)}</td>
							<td class="px-3 py-2 text-right" style="color:#383832;">{fmtNum(row.avg_sales, 0)}</td>
							<td class="px-3 py-2 text-right" style="color:#383832;">{fmtNum(row.daily_cost, 0)}</td>
							<td class="px-3 py-2 text-right font-bold" style="color:#383832;">{fmtNum(row.diesel_pct, 1)}%</td>
							<td class="px-3 py-2 text-center">
								<span
									class="inline-block px-3 py-1 text-[10px] font-black uppercase"
									style="background:{beColor(row.recommendation)};color:#feffd6;border:1px solid #383832;"
								>
									{row.recommendation || 'N/A'}
								</span>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{:else}
		<p class="text-xs" style="color:#65655e;">No break-even data available.</p>
	{/if}
</div>

<!-- ============ SECTION 6: MAPPED SITES ============ -->
<div class="mb-8">
	<div class="px-4 py-2 mb-4 flex items-center justify-between" style="background:#383832;border:2px solid #383832;">
		<h2 class="text-sm font-black uppercase tracking-wider" style="color:#feffd6;">MAPPED_SITES</h2>
		<div class="flex items-center gap-3">
			<span class="px-2 py-0.5 text-[10px] font-black" style="background:#007518;color:#feffd6;">{mappedCount}</span>
			<button onclick={() => downloadExcel(filteredMapped, 'Mapped Sites')}
				class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
				style="color: #00fc40;">
				<span class="material-symbols-outlined text-sm">download</span> EXCEL
			</button>
		</div>
	</div>

	{#if mapped.length > 0}
		<div class="overflow-x-auto" style="border:2px solid #383832;">
			<table class="w-full text-xs" style="background:#feffd6;">
				<thead>
					<tr style="background:#ebe8dd;">
						<th class="px-3 py-1.5 text-left font-black uppercase tracking-wider" style="color:#383832;border-bottom:2px solid #383832;">SITE_ID</th>
						<th class="px-3 py-1.5 text-left font-black uppercase tracking-wider" style="color:#383832;border-bottom:2px solid #383832;">SECTOR</th>
						<th class="px-3 py-1.5 text-left font-black uppercase tracking-wider" style="color:#383832;border-bottom:2px solid #383832;">SEGMENT</th>
						<th class="px-3 py-1.5 text-left font-black uppercase tracking-wider" style="color:#383832;border-bottom:2px solid #383832;">LOCATION</th>
						<th class="px-3 py-1.5 text-left font-black uppercase tracking-wider" style="color:#383832;border-bottom:2px solid #383832;">COST_CENTER</th>
						<th class="px-3 py-1.5 text-right font-black uppercase tracking-wider" style="color:#383832;border-bottom:2px solid #383832;">SALES_DAYS</th>
						<th class="px-3 py-1.5 text-right font-black uppercase tracking-wider" style="color:#383832;border-bottom:2px solid #383832;">TOTAL_SALES</th>
					</tr>
				</thead>
				<tbody>
					{#each filteredMapped as row, i}
						<tr style="background:{i % 2 === 0 ? '#feffd6' : '#f6f4e0'};border-top:1px solid #383832;">
							<td class="px-3 py-1.5 font-bold uppercase" style="color:#383832;">{row.site_id || '-'}</td>
							<td class="px-3 py-1.5 uppercase" style="color:#383832;">{row.sector || '-'}</td>
							<td class="px-3 py-1.5 text-xs" style="color:#383832;">{row.segment_name || ''}</td>
							<td class="px-3 py-1.5 text-xs" style="color:#383832;">{row.address_state || ''}</td>
							<td class="px-3 py-1.5" style="color:#383832;">{row.cost_center || '-'}</td>
							<td class="px-3 py-1.5 text-right" style="color:#383832;">{row.sales_days ?? '-'}</td>
							<td class="px-3 py-1.5 text-right" style="color:#383832;">{fmtNum(row.total_sales, 0)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{:else}
		<p class="text-xs" style="color:#65655e;">No mapped sites data available.</p>
	{/if}
</div>

<!-- ============ SECTION 7: UNMAPPED SITES ============ -->
<div class="mb-8">
	<div class="px-4 py-2 mb-4 flex items-center justify-between" style="background:#383832;border:2px solid #383832;">
		<h2 class="text-sm font-black uppercase tracking-wider" style="color:#feffd6;">UNMAPPED_SITES</h2>
		<div class="flex items-center gap-3">
			<span class="px-2 py-0.5 text-[10px] font-black" style="background:{unmappedCount > 0 ? '#be2d06' : '#007518'};color:#feffd6;">{unmappedCount}</span>
			<button onclick={() => downloadExcel(filteredUnmapped, 'Unmapped Sites')}
				class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
				style="color: #00fc40;">
				<span class="material-symbols-outlined text-sm">download</span> EXCEL
			</button>
		</div>
	</div>

	{#if unmapped.length > 0}
		<div class="p-3 mb-3 text-xs font-bold" style="background:#feffd6;border:2px solid #ff9d00;color:#be2d06;">
			These sites have no sales data &mdash; diesel% cannot be calculated
		</div>
		<div class="overflow-x-auto" style="border:2px solid #383832;">
			<table class="w-full text-xs" style="background:#feffd6;">
				<thead>
					<tr style="background:#ebe8dd;">
						<th class="px-3 py-1.5 text-left font-black uppercase tracking-wider" style="color:#383832;border-bottom:2px solid #383832;">SITE_ID</th>
						<th class="px-3 py-1.5 text-left font-black uppercase tracking-wider" style="color:#383832;border-bottom:2px solid #383832;">SECTOR</th>
						<th class="px-3 py-1.5 text-left font-black uppercase tracking-wider" style="color:#383832;border-bottom:2px solid #383832;">SEGMENT</th>
						<th class="px-3 py-1.5 text-left font-black uppercase tracking-wider" style="color:#383832;border-bottom:2px solid #383832;">LOCATION</th>
						<th class="px-3 py-1.5 text-left font-black uppercase tracking-wider" style="color:#383832;border-bottom:2px solid #383832;">SITE_NAME</th>
						<th class="px-3 py-1.5 text-left font-black uppercase tracking-wider" style="color:#383832;border-bottom:2px solid #383832;">COST_CENTER</th>
					</tr>
				</thead>
				<tbody>
					{#each filteredUnmapped as row, i}
						<tr style="background:{i % 2 === 0 ? '#feffd6' : '#f6f4e0'};border-top:1px solid #383832;">
							<td class="px-3 py-1.5 font-bold uppercase" style="color:#383832;">{row.site_id || '-'}</td>
							<td class="px-3 py-1.5 uppercase" style="color:#383832;">{row.sector || '-'}</td>
							<td class="px-3 py-1.5 text-xs" style="color:#383832;">{row.segment_name || ''}</td>
							<td class="px-3 py-1.5 text-xs" style="color:#383832;">{row.address_state || ''}</td>
							<td class="px-3 py-1.5" style="color:#383832;">{row.site_name || '-'}</td>
							<td class="px-3 py-1.5" style="color:#383832;">{row.cost_center || '-'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{:else}
		<p class="text-xs" style="color:#65655e;">All sites are mapped.</p>
	{/if}
</div>

<!-- Ocean Cost Allocation -->
{#if oceanAlloc.stores && oceanAlloc.stores.length > 0}
	{@const fmtC = (v: number) => v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(1)+'K' : v.toLocaleString()}
	<div class="mt-6" style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
		<div class="px-4 py-2 flex justify-between items-center" style="background: #006f7c; color: white;">
			<div>
				<span class="font-black uppercase text-sm">OCEAN COST ALLOCATION</span>
				<span class="text-[10px] ml-2 opacity-75">Ocean diesel cost = Center diesel (CP) × Store Contribution %</span>
			</div>
			<button onclick={() => downloadExcel(oceanAlloc.stores, 'Ocean Cost Allocation')}
				class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100" style="color: #00fc40;">
				<span class="material-symbols-outlined text-sm">download</span> EXCEL
			</button>
		</div>

		<!-- Summary KPIs -->
		<div class="grid grid-cols-2 md:grid-cols-4 gap-0" style="border-bottom: 2px solid #383832;">
			<div class="p-3 text-center" style="background: white; border-right: 1px solid #ebe8dd;">
				<div class="text-2xl font-black" style="color: #383832;">{oceanAlloc.stores.length}</div>
				<div class="text-[10px] font-bold">OCEAN STORES</div>
			</div>
			<div class="p-3 text-center" style="background: white; border-right: 1px solid #ebe8dd;">
				<div class="text-2xl font-black" style="color: #383832;">{fmtC(oceanAlloc.total_center_cost)}</div>
				<div class="text-[10px] font-bold">CENTER TOTAL COST</div>
				<div class="text-[8px]" style="color: #65655e;">all centers combined</div>
			</div>
			<div class="p-3 text-center" style="background: white; border-right: 1px solid #ebe8dd;">
				<div class="text-2xl font-black" style="color: #006f7c;">{fmtC(oceanAlloc.total_ocean_share)}</div>
				<div class="text-[10px] font-bold">OCEAN'S SHARE</div>
				<div class="text-[8px]" style="color: #65655e;">after contribution % split</div>
			</div>
			<div class="p-3 text-center" style="background: white;">
				<div class="text-2xl font-black" style="color: #007518;">{fmtC(oceanAlloc.total_center_cost - oceanAlloc.total_ocean_share)}</div>
				<div class="text-[10px] font-bold">SHARED WITH CENTER</div>
				<div class="text-[8px]" style="color: #65655e;">({oceanAlloc.total_center_cost > 0 ? ((1 - oceanAlloc.total_ocean_share / oceanAlloc.total_center_cost) * 100).toFixed(0) : 0}% paid by others)</div>
			</div>
		</div>

		<!-- Formula -->
		<div class="px-3 py-1.5 text-[9px] font-mono" style="background: #ebe8dd; color: #65655e; border-bottom: 1px solid #383832;">
			Stand Alone: Ocean Cost = Own Diesel Used × CMHL Price | Shopping Center: Ocean Cost = CP Center Diesel × Contribution %
		</div>

		<!-- Table -->
		<div class="overflow-x-auto overflow-y-auto" style="max-height: 400px;">
			<table class="w-full text-xs">
				<thead class="sticky top-0 z-10">
					<tr style="background: #ebe8dd;">
						<th class="py-2 px-2 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">OCEAN STORE</th>
						<th class="py-2 px-2 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">NAME</th>
						<th class="py-2 px-2 text-center font-black uppercase" style="border-bottom: 2px solid #383832;">CENTER</th>
						<th class="py-2 px-2 text-center font-black uppercase" style="border-bottom: 2px solid #383832;">TYPE</th>
						<th class="py-2 px-2 text-center font-black uppercase" style="border-bottom: 2px solid #383832;">CTR FUEL(L)</th>
						<th class="py-2 px-2 text-center font-black uppercase" style="border-bottom: 2px solid #383832;">CTR COST</th>
						<th class="py-2 px-2 text-center font-black uppercase" style="border-bottom: 2px solid #383832;">CONTRIB %</th>
						<th class="py-2 px-2 text-center font-black uppercase" style="border-bottom: 2px solid #383832; color: #006f7c;">OCEAN COST</th>
					</tr>
				</thead>
				<tbody>
					{#each oceanAlloc.stores as s, i}
						<tr style="background: {i % 2 ? '#f6f4e9' : 'white'}; border-bottom: 1px solid #ebe8dd;">
							<td class="py-2 px-2 font-bold" style="color: #383832;">{s.ocean_site}</td>
							<td class="py-2 px-2" style="color: #383832;">{s.ocean_name}</td>
							<td class="py-2 px-2 text-center font-mono" style="color: #65655e;">{s.center_cc}</td>
							<td class="py-2 px-2 text-center">
								<span class="px-2 py-0.5 text-[9px] font-bold uppercase" style="background: {s.type === 'Stand Alone' ? '#383832' : '#006f7c'}; color: white;">{s.type === 'Shopping Center' ? 'SHARED' : 'STAND ALONE'}</span>
							</td>
							<td class="py-2 px-2 text-center font-mono">{s.center_fuel.toLocaleString()}</td>
							<td class="py-2 px-2 text-center font-mono">{fmtC(s.center_cost)}</td>
							<td class="py-2 px-2 text-center font-black" style="color: {s.pct < 1 ? '#006f7c' : '#383832'};">{(s.pct * 100).toFixed(0)}%</td>
							<td class="py-2 px-2 text-center font-black" style="color: #006f7c;">{fmtC(s.ocean_cost)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</div>
{/if}

{/if}
