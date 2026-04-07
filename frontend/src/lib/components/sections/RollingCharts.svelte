<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import Chart from '$lib/components/Chart.svelte';
	import { lineChart, dualAxisChart } from '$lib/charts';

	// Sector rolling chart guides
	const sectorGuides = {
		fuel: { formula: 'Total diesel liters per sector per day, <b>3-day smoothed</b>.', sources: [{ data: 'Fuel', file: 'Blackout Hr Excel', col: 'Daily Used', method: 'SUM + 3d rolling' }], reading: [{ color: 'green', text: '✅ Flat = Stable consumption' }, { color: 'red', text: '🔴 Rising line = Sector burning more fuel' }], explain: 'Each line is a <b>sector</b>. Smoothed to remove daily noise. Rising = that area needs attention.' },
		efficiency: { formula: 'Sector-level L/Hr, <b>3-day smoothed</b>. Lower = more efficient.', sources: [{ data: 'Efficiency', file: 'Blackout Hr Excel', col: 'Used ÷ Hours', method: 'AVG + 3d rolling' }], reading: [{ color: 'green', text: '✅ Flat (15-20) = Healthy' }, { color: 'red', text: '🔴 Rising = Fuel waste in that sector' }], explain: 'Compares <b>fuel economy</b> across sectors. If one line rises, those generators need maintenance.' },
		cost: { formula: 'Fuel liters × price per sector, <b>3-day smoothed</b>.', sources: [{ data: 'Cost', file: 'Blackout + Fuel Price', col: 'Used × Price', method: 'SUM + 3d rolling' }], reading: [{ color: 'green', text: '✅ Flat = Budget on track' }, { color: 'red', text: '🔴 Rising = Budget pressure' }], explain: 'Total diesel <b>spend per sector</b> over time. Smoothed to show real trends, not daily spikes.' },
		blackout: { formula: 'Average blackout hours per sector, <b>3-day smoothed</b>.', sources: [{ data: 'Blackout', file: 'Blackout Hr Excel', col: 'Blackout Hr', method: 'AVG + 3d rolling' }], reading: [{ color: 'green', text: '✅ Dropping = Grid improving' }, { color: 'red', text: '🔴 Rising = More power outages' }], explain: 'Shows <b>power grid quality</b> per sector. Rising = worse blackouts, plan for more generator fuel.' },
	};

	let { dateFrom = '', dateTo = '', sector = '', window = 3 }: { dateFrom?: string; dateTo?: string; sector?: string; window?: number } = $props();

	let daily: any[] = $state([]);
	let sectorData: Record<string, any[]> = $state({});
	let loading = $state(true);
	const sectorColors: Record<string, string> = { CMHL: '#FF9800', CP: '#2196F3', CFC: '#4CAF50', PG: '#9C27B0' };

	async function load() {
		loading = true;
		const p = new URLSearchParams();
		if (dateFrom) p.set('date_from', dateFrom);
		if (dateTo) p.set('date_to', dateTo);
		if (sector) p.set('sector', sector);
		const [d, sr] = await Promise.all([
			api.get(`/daily-summary?${p}`),
			api.get(`/trends/rolling-sector?${p}`),
		]);
		daily = d;
		sectorData = sr?.sectors || {};
		loading = false;
	}

	onMount(load);

	function rolling(vals: number[], w: number): number[] {
		return vals.map((_, i) => {
			const start = Math.max(0, i - w + 1);
			const slice = vals.slice(start, i + 1);
			return Math.round(slice.reduce((a, b) => a + b, 0) / slice.length);
		});
	}

	function buildData() {
		const dateMap = new Map<string, { liters: number; hours: number; tank: number; crit: number }>();
		for (const r of daily) {
			const d = r.date;
			if (!dateMap.has(d)) dateMap.set(d, { liters: 0, hours: 0, tank: 0, crit: 0 });
			const m = dateMap.get(d)!;
			m.liters += r.total_daily_used || 0;
			m.hours += r.total_gen_run_hr || 0;
			m.tank += r.spare_tank_balance || 0;
			m.crit += (r.days_of_buffer || 99) < 3 ? 1 : 0;
		}
		const dates = [...dateMap.keys()].sort();
		const liters = dates.map(d => Math.round(dateMap.get(d)!.liters));
		const hours = dates.map(d => Math.round(dateMap.get(d)!.hours));
		const tank = dates.map(d => Math.round(dateMap.get(d)!.tank));
		const eff = liters.map((l, i) => hours[i] > 0 ? Math.round(l / hours[i] * 10) / 10 : 0);
		const buf = tank.map((t, i) => liters[i] > 0 ? Math.round(t / liters[i] * 10) / 10 : 0);
		const crit = dates.map(d => dateMap.get(d)!.crit);
		return { dates, liters, hours, eff, buf, crit, rLiters: rolling(liters, window), rHours: rolling(hours, window), rEff: rolling(eff, window), rBuf: rolling(buf, window), rCrit: rolling(crit, window) };
	}

	const wl = `${window}-Day Avg`;
</script>

{#if loading}
	<div class="space-y-4 py-4">
		<div class="skeleton h-5 w-48"></div>
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
			<div class="skeleton h-[300px]"></div>
			<div class="skeleton h-[300px]"></div>
		</div>
		<div class="skeleton h-5 w-36 mt-4"></div>
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
			<div class="skeleton h-[300px]"></div>
			<div class="skeleton h-[300px]"></div>
		</div>
	</div>
{:else if daily.length < window * 2}
	<p class="text-sm py-4 text-center" style="color: #65655e;">Need at least {window * 2} days of data for rolling averages. Try a wider date range.</p>
{:else}
	{@const d = buildData()}

	<!-- ═══ CHAPTER 6: ROLLING TRENDS ═══ -->
	<div id="ch-rolling" class="scroll-mt-36">
		<div class="flex items-center gap-3 px-4 py-3 mb-4 mt-4" style="background: #383832; color: #feffd6;">
			<span class="material-symbols-outlined text-xl" style="color: #00fc40;">trending_up</span>
			<div>
				<div class="font-black uppercase text-sm">CHAPTER 6: ROLLING TRENDS ({wl})</div>
				<div class="text-[10px] opacity-75">Smoothed trends removing daily noise — see the real direction</div>
			</div>
		</div>
	</div>
	<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
		<Chart option={lineChart(d.dates, [
			{ name: 'Daily Fuel (L)', data: d.liters, color: '#fca5a5' },
			{ name: `${wl} Fuel`, data: d.rLiters, color: '#ef4444' }
		], { title: `Fuel Burn — Daily vs ${wl}` })} guide={{ formula: `Solid line = daily diesel used. Dashed = ${wl} rolling average.`, sources: [{ data: 'Diesel Used', file: 'Blackout Hr Excel', col: 'Daily Used', method: `SUM + ${wl} rolling` }], reading: [{ color: 'green', text: '✅ Lines track closely = Stable consumption' }, { color: 'red', text: '🔴 Lines diverging = Trend change' }], explain: `Daily numbers bounce like <b>daily weather</b>. The smooth line is the <b>forecast</b> — shows the real trend.` }} />

		<Chart option={lineChart(d.dates, [
			{ name: 'Daily Buffer', data: d.buf, color: '#93c5fd' },
			{ name: `${wl} Buffer`, data: d.rBuf, color: '#3b82f6' }
		], { title: `Buffer Days — Daily vs ${wl}`, markLines: [{ value: 7, label: 'Safe', color: '#16a34a' }, { value: 3, label: 'Critical', color: '#dc2626' }] })} guide={{ formula: `Solid line = daily buffer days. Dashed = ${wl} rolling average.`, sources: [{ data: 'Buffer', file: 'Blackout Hr Excel', col: 'Tank ÷ Daily Used', method: `${wl} rolling` }], reading: [{ color: 'green', text: '🟢 Above 7 = Safe' }, { color: 'red', text: '🔴 Below 3 = Danger' }], explain: `Like your <b>phone battery</b>. Smoothed line dropping = fuel running out over time.` }} />

		<Chart option={lineChart(d.dates, [
			{ name: 'Daily Gen Hr', data: d.hours, color: '#93c5fd' },
			{ name: `${wl} Gen Hr`, data: d.rHours, color: '#3b82f6' }
		], { title: `Gen Hours — Daily vs ${wl}` })} guide={{ formula: `Solid line = daily generator hours. Dashed = ${wl} rolling average.`, sources: [{ data: 'Gen Hours', file: 'Blackout Hr Excel', col: 'Gen Run Hr', method: `SUM + ${wl} rolling` }], reading: [{ color: 'green', text: '✅ Lines track closely = Stable blackout pattern' }, { color: 'red', text: '🔴 Rising smooth line = Blackouts getting longer' }], explain: `Total hours generators ran. Rising smooth line = <b>grid getting worse</b>.` }} />

		<Chart option={lineChart(d.dates, [
			{ name: 'Daily L/Hr', data: d.eff, color: '#c4b5fd' },
			{ name: `${wl} L/Hr`, data: d.rEff, color: '#8b5cf6' }
		], { title: `Efficiency — Daily vs ${wl}` })} guide={{ formula: `Solid line = daily L/Hr. Dashed = ${wl} rolling average.`, sources: [{ data: 'Efficiency', file: 'Blackout Hr Excel', col: 'Daily Used ÷ Gen Run Hr', method: `${wl} rolling` }], reading: [{ color: 'green', text: '✅ Flat lines = Healthy generators' }, { color: 'red', text: '🔴 Rising = Fuel waste or theft' }], explain: `Fuel efficiency smoothed. Rising = generators <b>burning more per hour</b> — investigate.` }} />

		<!-- #24 Gen Hours vs Fuel (dual-axis rolling) -->
		<Chart option={dualAxisChart(d.dates, d.rHours, d.rLiters,
			{ title: `Gen Hours vs Fuel (${wl})`, barName: `Gen Hours (${wl})`, lineName: `Fuel (${wl})`, barColor: '#3b82f6', lineColor: '#ef4444' }
		)} guide={{ formula: `${wl} rolling average of total gen hours (bars) vs total fuel (line).`, sources: [{ data: 'Gen Hours', file: 'Blackout Hr Excel', col: 'Gen Run Hr', method: `SUM + ${wl} rolling` }, { data: 'Fuel', file: 'Blackout Hr Excel', col: 'Daily Used', method: `SUM + ${wl} rolling` }], reading: [{ color: 'green', text: '✅ Both move together = Normal' }, { color: 'red', text: '🔴 Line rises, bars flat = Waste' }], explain: `Smoothed comparison of <b>hours vs fuel</b>. Divergence = investigate.` }} />

		<!-- #28 Buffer Days Rolling (Risk) -->
		<Chart option={lineChart(d.dates, [
			{ name: 'Daily Buffer', data: d.buf, color: '#93c5fd' },
			{ name: `${wl} Buffer`, data: d.rBuf, color: '#3b82f6' }
		], { title: `Buffer Days — ${wl} (Risk View)`, markLines: [{ value: 7, label: 'Safe', color: '#16a34a' }, { value: 3, label: 'Critical', color: '#dc2626' }] })} guide={{ formula: `Buffer days with ${wl} smoothing. Below 3 = CRITICAL.`, sources: [{ data: 'Buffer', file: 'Blackout Hr Excel', col: 'Tank ÷ Used', method: `${wl} rolling` }], reading: [{ color: 'green', text: '🟢 Above 7 = Safe zone' }, { color: 'amber', text: '🟡 3-7 = Warning zone' }, { color: 'red', text: '🔴 Below 3 = CRITICAL' }], explain: `Shows if fuel is <b>gradually running out</b>. Downward trend = plan deliveries.` }} />

		<!-- #29 Critical Sites Rolling -->
		<Chart option={lineChart(d.dates, [
			{ name: 'Daily Critical', data: d.crit, color: '#fca5a5' },
			{ name: `${wl} Critical`, data: d.rCrit, color: '#dc2626' }
		], { title: `Critical Sites (<3d buffer) — ${wl}` })} guide={{ formula: `Count of sites with < 3 days buffer, ${wl} smoothed.`, sources: [{ data: 'Critical Count', file: 'Blackout Hr Excel', col: 'Buffer < 3', method: `COUNT + ${wl} rolling` }], reading: [{ color: 'green', text: '✅ Zero = No emergencies' }, { color: 'red', text: '🔴 Rising = More sites in danger' }], explain: `How many sites are in the <b>danger zone</b>. Rising smooth line = systemic problem, not just a bad day.` }} />
	</div>

	<!-- Sector Rolling Breakdowns -->
	{#if Object.keys(sectorData).length > 0}
		{@const allSectors = Object.keys(sectorData).sort()}
		{@const allDates = allSectors.length > 0 ? sectorData[allSectors[0]].map((r: any) => r.date) : []}

		<h3 class="text-base font-black uppercase mt-8 mb-3 px-3 py-1" style="background: #383832; color: #feffd6;">SECTOR ROLLING BREAKDOWNS</h3>
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
			<Chart option={lineChart(allDates,
				allSectors.map(s => ({
					name: s + ' (rolling)',
					data: (sectorData[s] || []).map((r: any) => Math.round(r.fuel_roll || 0)),
					color: sectorColors[s] || '#6b7280'
				})),
				{ title: 'Fuel by Sector — 3-Day Rolling' }
			)} guide={sectorGuides.fuel} />

			<Chart option={lineChart(allDates,
				allSectors.map(s => ({
					name: s + ' (rolling)',
					data: (sectorData[s] || []).map((r: any) => Math.round((r.efficiency_roll || 0) * 10) / 10),
					color: sectorColors[s] || '#6b7280'
				})),
				{ title: 'Efficiency by Sector — 3-Day Rolling L/Hr' }
			)} guide={sectorGuides.efficiency} />

			<Chart option={lineChart(allDates,
				allSectors.flatMap(s => [
					{ name: s + ' Fuel', data: (sectorData[s] || []).map((r: any) => Math.round(r.fuel_roll || 0)), color: sectorColors[s] || '#6b7280' },
				]),
				{ title: 'Fuel Rolling — by Sector' }
			)} guide={{ formula: 'One line per sector, 3-day rolling average of fuel used.', sources: [{ data: 'Fuel', file: 'Blackout Hr Excel', col: 'Daily Used', method: 'SUM + 3d rolling' }], reading: [{ color: 'green', text: '✅ Lines flat = Stable across sectors' }, { color: 'red', text: '🔴 One line rising = That sector burning more' }], explain: 'Compare <b>fuel trends</b> across sectors side by side. Rising line = that area needs attention.' }} />

			<Chart option={lineChart(allDates,
				allSectors.map(s => ({
					name: s + ' Cost',
					data: (sectorData[s] || []).map((r: any) => Math.round(r.cost_roll || 0)),
					color: sectorColors[s] || '#6b7280'
				})),
				{ title: 'Diesel Cost by Sector — 3-Day Rolling' }
			)} guide={sectorGuides.cost} />

			<Chart option={lineChart(allDates,
				allSectors.map(s => ({
					name: s,
					data: (sectorData[s] || []).map((r: any) => Math.round((r.blackout_roll || 0) * 10) / 10),
					color: sectorColors[s] || '#6b7280'
				})),
				{ title: 'Blackout Hours — 3-Day Rolling' }
			)} guide={sectorGuides.blackout} />

			<!-- Sales vs Diesel (if available) -->
			{#if allSectors.some(s => (sectorData[s] || []).some((r: any) => r.sales_roll))}
				<div>
					<Chart option={lineChart(allDates,
						allSectors.map(s => ({
							name: s + ' Diesel%',
							data: (sectorData[s] || []).map((r: any) => Math.round((r.diesel_pct_roll || 0) * 10) / 10),
							color: sectorColors[s] || '#6b7280'
						})),
						{ title: 'Diesel % of Sales — 3-Day Rolling' }
					)} guide={{ formula: 'One line per sector, 3-day rolling average of (Diesel Cost ÷ Sales × 100).', sources: [{ data: 'Diesel %', file: 'Blackout + Sales', col: 'Cost ÷ Sales', method: 'AVG + 3d rolling' }], reading: [{ color: 'green', text: '✅ Below 5% = Healthy ratio' }, { color: 'red', text: '🔴 Rising = Fuel eating into revenue' }], explain: 'Shows how much of each sector\'s <b>revenue goes to diesel</b>. Rising = profits shrinking.' }} />
				</div>

				<div>
					<Chart option={lineChart(allDates,
						allSectors.map(s => ({
							name: s + ' Sales',
							data: (sectorData[s] || []).map((r: any) => Math.round((r.sales_roll || 0) / 1e6 * 10) / 10),
							color: sectorColors[s] || '#6b7280'
						})),
						{ title: 'Sales by Sector — 3-Day Rolling (M)' }
					)} guide={{ formula: 'One line per sector, 3-day rolling average of daily sales (in millions).', sources: [{ data: 'Sales', file: 'Sales Excel', col: 'Daily Sales', method: 'SUM + 3d rolling' }], reading: [{ color: 'green', text: '✅ Rising = Revenue growing' }, { color: 'red', text: '🔴 Dropping = Revenue declining' }], explain: 'Tracks <b>revenue trends</b> per sector. Compare with diesel cost lines to see profitability.' }} />
				</div>
			{/if}
		</div>
	{/if}
{/if}
