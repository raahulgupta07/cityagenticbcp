<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import Chart from '$lib/components/Chart.svelte';
	import { barChart, lineChart, dualAxisChart } from '$lib/charts';

	let { dateFrom = '', dateTo = '', sector = '' }: { dateFrom?: string; dateTo?: string; sector?: string } = $props();

	let daily: any[] = $state([]);
	let fuelPrices: any[] = $state([]);
	let salesData: any[] = $state([]);
	let loading = $state(true);
	let error = $state('');

	async function load() {
		loading = true;
		error = '';
		const p = new URLSearchParams();
		if (dateFrom) p.set('date_from', dateFrom);
		if (dateTo) p.set('date_to', dateTo);
		if (sector) p.set('sector', sector);
		try {
			const [d, fp, sd] = await Promise.all([
				api.get(`/daily-summary?${p}`),
				api.get(`/fuel-prices?${p}`).catch(() => []),
				api.get(`/sales?${p}`).catch(() => []),
			]);
			daily = d;
			fuelPrices = fp;
			salesData = sd;
		} catch (e) {
			console.error(e);
			error = 'Failed to load trend data. Check your connection and try again.';
		} finally {
			loading = false;
		}
	}

	onMount(load);
	$effect(() => { dateFrom; dateTo; sector; load(); });

	// Build price lookup: sector → date → price (latest purchase on or before that date)
	function priceOnDate(sectorId: string, date: string): number {
		let best = 0;
		for (const fp of fuelPrices) {
			if (fp.sector_id === sectorId && fp.date <= date && fp.price_per_liter > 0) {
				if (!best || fp.date > (fuelPrices.find((f: any) => f.price_per_liter === best)?.date || '')) best = fp.price_per_liter;
			}
		}
		if (!best) {
			// Fallback: any sector price
			for (const fp of fuelPrices) {
				if (fp.date <= date && fp.price_per_liter > 0) best = fp.price_per_liter;
			}
		}
		return best;
	}

	function byDate() {
		const map = new Map<string, { hours: number; liters: number; tank: number; sites: number; crit: number; blackout: number; boSites: number; sectors: Map<string, { h: number; l: number; n: number; bo: number; boN: number }> }>();
		for (const r of daily) {
			const d = r.date;
			if (!map.has(d)) map.set(d, { hours: 0, liters: 0, tank: 0, sites: 0, crit: 0, blackout: 0, boSites: 0, sectors: new Map() });
			const m = map.get(d)!;
			m.hours += r.total_gen_run_hr || 0;
			m.liters += r.total_daily_used || 0;
			m.tank += r.spare_tank_balance || 0;
			m.sites += 1;
			m.crit += (r.days_of_buffer || 99) < 3 ? 1 : 0;
			if (r.blackout_hr != null && r.blackout_hr !== '') { m.blackout += r.blackout_hr; m.boSites += 1; }
			const sid = r.sector_id || '?';
			if (!m.sectors.has(sid)) m.sectors.set(sid, { h: 0, l: 0, n: 0, bo: 0, boN: 0 });
			const s = m.sectors.get(sid)!;
			s.h += r.total_gen_run_hr || 0;
			s.l += r.total_daily_used || 0;
			s.n += 1;
			if (r.blackout_hr != null && r.blackout_hr !== '') { s.bo += r.blackout_hr; s.boN += 1; }
		}
		const dates = [...map.keys()].sort();
		return { dates, map };
	}

	// Aggregate sales by date
	function salesByDate(): Map<string, number> {
		const m = new Map<string, number>();
		for (const r of salesData) {
			const d = r.date;
			m.set(d, (m.get(d) || 0) + (r.sales_amt || 0));
		}
		return m;
	}

	// Compute diesel cost per date (liters × price)
	function costByDate(dates: string[], map: Map<string, any>): number[] {
		return dates.map(d => {
			const m = map.get(d)!;
			// Use first sector's price as approximation, or average across sectors
			let totalCost = 0;
			for (const [sid, sec] of m.sectors) {
				const price = priceOnDate(sid, d);
				totalCost += (sec as any).l * price;
			}
			return totalCost;
		});
	}

	function allSectors() {
		return [...new Set(daily.map((r: any) => r.sector_id).filter(Boolean))].sort();
	}

	const sectorColors: Record<string, string> = { CMHL: '#FF9800', CP: '#2196F3', CFC: '#4CAF50', PG: '#9C27B0' };
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
{:else if error}
	<div class="text-center py-12" style="background: #f6f4e9; border: 2px solid #383832;">
		<span class="material-symbols-outlined text-3xl" style="color: #be2d06;">error</span>
		<p class="font-bold mt-2 uppercase text-xs" style="color: #be2d06;">{error}</p>
		<button onclick={load} class="mt-3 px-4 py-1.5 text-[10px] font-black uppercase"
			style="background: #383832; color: #feffd6; border: 2px solid #383832;">
			<span class="material-symbols-outlined text-xs align-middle">refresh</span> RETRY
		</button>
	</div>
{:else if daily.length === 0}
	<div class="text-center py-12" style="background: #f6f4e9; border: 2px solid #383832;">
		<span class="material-symbols-outlined text-3xl" style="color: #65655e;">inbox</span>
		<p class="font-bold mt-2 uppercase text-xs" style="color: #383832;">NO DATA AVAILABLE</p>
		<p class="text-[10px] mt-1" style="color: #65655e;">Upload data or adjust your filters.</p>
	</div>
{:else if daily.length < 2}
	<div class="text-center py-12" style="background: #f6f4e9; border: 2px solid #383832;">
		<span class="material-symbols-outlined text-3xl" style="color: #65655e;">show_chart</span>
		<p class="font-bold mt-2 uppercase text-xs" style="color: #383832;">INSUFFICIENT DATA FOR TRENDS</p>
		<p class="text-[10px] mt-1" style="color: #65655e;">Need at least 2 days of data. Try selecting a wider date range or a different sector.</p>
	</div>
{:else}
	{@const { dates, map } = byDate()}
	{@const sectors = allSectors()}

	<!-- ═══ CHAPTER 1: THE POWER WENT OUT ═══ -->
	<div id="ch-blackout" class="scroll-mt-36">
		<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
			<div class="flex items-center gap-3">
				<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">power_off</span>
				<div>
					<div class="font-black uppercase text-sm">CHAPTER 1: THE POWER WENT OUT</div>
					<div class="text-[10px] opacity-75">How bad were the blackouts? This is the root cause of all diesel consumption.</div>
				</div>
			</div>
			<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">
				? How many hours were sites without power? Which sectors had the worst grid?
			</div>
		</div>
	</div>
	<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
		<!-- Blackout vs Fuel -->
		<Chart option={dualAxisChart(dates,
			dates.map(d => { const m = map.get(d)!; return m.boSites > 0 ? Math.round(m.blackout / m.boSites * 10) / 10 : 0; }),
			dates.map(d => { const m = map.get(d)!; return m.sites > 0 ? Math.round(m.liters / m.sites) : 0; }),
			{ title: 'Avg Blackout Hr vs Avg Fuel per Site', barName: 'Avg Blackout Hr', lineName: 'Avg Fuel (L)', barColor: '#d97706', lineColor: '#ef4444' }
		)} guide={{
			formula: "Amber bars = AVG blackout hours per site. Red line = AVG fuel liters per site.",
			sources: [{ data: 'Blackout Hours', file: 'Blackout Hr Excel', col: 'Blackout Hr', method: 'AVG per site' }, { data: 'Fuel Used', file: 'Blackout Hr Excel', col: 'Daily Used', method: 'AVG per site' }],
			reading: [{ color: 'green', text: '✅ Both low = Good grid power' }, { color: 'amber', text: '⚠️ Bars rise = More blackouts' }, { color: 'red', text: '🔴 Line rises without bars = Fuel waste' }],
			explain: "Shows the <b>relationship between blackouts and fuel</b>. They should move together."
		}} />
		<!-- Blackout by Sector -->
		<Chart option={lineChart(dates,
			sectors.map(s => ({
				name: s,
				data: dates.map(d => {
					const sec = map.get(d)!.sectors.get(s);
					return sec && (sec as any).boN > 0 ? Math.round((sec as any).bo / (sec as any).boN * 10) / 10 : 0;
				}),
				color: sectorColors[s] || '#6b7280'
			})),
			{ title: 'Avg Blackout Hours per Site by Sector' }
		)} guide={{
			formula: "AVG(Blackout Hours) per site, one line per sector.",
			sources: [{ data: 'Blackout Hours', file: 'Blackout Hr Excel', col: 'Blackout Hr', method: 'AVG per sector per day' }],
			reading: [{ color: 'green', text: '✅ Low (0-4 hr) = Minimal blackouts' }, { color: 'red', text: '🔴 12+ hr = Near-total blackout' }],
			explain: "Shows which <b>sector suffers the most blackouts</b>. Higher = worse grid."
		}} />
	</div>

	<!-- ═══ CHAPTER 2: SO WE BURNED FUEL ═══ -->
	<div id="ch-fuel" class="scroll-mt-36">
		<div class="px-4 py-3 mb-3" style="background: #383832; color: #feffd6;">
			<div class="flex items-center gap-3">
				<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">local_gas_station</span>
				<div>
					<div class="font-black uppercase text-sm">CHAPTER 2: SO WE BURNED FUEL</div>
					<div class="text-[10px] opacity-75">Blackouts forced generators to run → fuel was consumed.</div>
				</div>
			</div>
			<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">
				? How many liters were consumed? Which sector used the most? Is our data complete?
			</div>
		</div>
	</div>

	<!-- Sites Reporting -->
	<Chart option={barChart(dates, dates.map(d => map.get(d)!.sites), { title: 'Sites Reporting per Day', color: '#64748b' })} height="200px" guide={{
		formula: "Number of sites that reported data each day.",
		sources: [{ data: 'Site count', file: 'Blackout Hr Excel', col: 'sites with data', method: 'COUNT' }],
		reading: [
			{ color: 'green', text: '✅ Full bar = All sites reported' },
			{ color: 'amber', text: '⚠️ Short bar = Some missing, totals understated' }
		],
		explain: "Like <b>attendance</b>. If half the class is absent, the average is unreliable."
	}} />

	<h3 class="text-base font-black uppercase mt-6 mb-3 px-3 py-1" style="background: #383832; color: #feffd6;">OVERALL — ALL SITES COMBINED</h3>
	<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
		<!-- Gen Hours vs Fuel -->
		<Chart option={dualAxisChart(dates,
			dates.map(d => Math.round(map.get(d)!.hours)),
			dates.map(d => Math.round(map.get(d)!.liters)),
			{ title: 'Generator Hours vs Fuel Consumption', barName: 'Gen Hours (hr)', lineName: 'Fuel Used (L)', barColor: '#3b82f6', lineColor: '#ef4444' }
		)} guide={{
			formula: "Blue bars = total hours generators ran. Red line = total diesel liters used.",
			sources: [
				{ data: 'Generator Hours', file: 'Blackout Hr Excel', col: 'Gen Run Hr', method: 'SUM all sites' },
				{ data: 'Diesel Used', file: 'Blackout Hr Excel', col: 'Daily Used', method: 'SUM all sites' }
			],
			reading: [
				{ color: 'green', text: '✅ Both move together = Normal' },
				{ color: 'amber', text: '⚠️ Red rises, bars flat = Waste or theft' },
				{ color: 'red', text: '🔴 Red spikes = Investigate that day' }
			],
			explain: "Like a <b>delivery truck</b>. Blue = hours driving. Red = petrol used. Both should track together. If petrol <b class='text-red-400'>doubles</b> without more driving, something is wrong."
		}} />

		<!-- Efficiency -->
		<Chart option={lineChart(dates,
			[{ name: 'L/Hr', data: dates.map(d => { const m = map.get(d)!; return m.hours > 0 ? Math.round(m.liters / m.hours * 10) / 10 : 0; }), color: '#8b5cf6' }],
			{ title: 'Overall Efficiency — Liters per Gen Hour' }
		)} guide={{
			formula: "Total diesel liters ÷ Total generator hours = <b>Liters per hour</b>.",
			sources: [
				{ data: 'Diesel Used', file: 'Blackout Hr Excel', col: 'Daily Used', method: 'SUM all sites' },
				{ data: 'Generator Hours', file: 'Blackout Hr Excel', col: 'Gen Run Hr', method: 'SUM all sites' }
			],
			reading: [
				{ color: 'green', text: '✅ Flat (15-20 L/Hr) = Healthy generators' },
				{ color: 'amber', text: '⚠️ Spike up = Waste or theft' },
				{ color: 'blue', text: '📉 Drop = Efficiency improving' }
			],
			explain: "Like your <b>car's fuel economy</b>. Flat = healthy. If it suddenly <b class='text-amber-400'>jumps up</b>, the engine needs checking — or someone is <b class='text-red-400'>stealing fuel</b>."
		}} />
	</div>

	<!-- By Sector -->
	<h3 class="text-base font-black uppercase mt-6 mb-3 px-3 py-1" style="background: #383832; color: #feffd6;">BY SECTOR BREAKDOWN</h3>
	<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
		<!-- Fuel by Sector -->
		<Chart option={lineChart(dates,
			sectors.map(s => ({
				name: s,
				data: dates.map(d => Math.round(map.get(d)!.sectors.get(s)?.l || 0)),
				color: sectorColors[s] || '#6b7280'
			})),
			{ title: 'Daily Fuel Consumption (L) — by Sector' }
		)} guide={{
			formula: "Total diesel liters per day, one line per sector.",
			sources: [{ data: 'Diesel Used', file: 'Blackout Hr Excel', col: 'Daily Used', method: 'SUM per sector per day' }],
			reading: [
				{ color: 'green', text: '✅ Stable lines = Predictable consumption' },
				{ color: 'red', text: '🔴 One sector spikes = Investigate that area' }
			],
			explain: "Each line is a <b>business sector</b>. The <b class='text-amber-400'>highest line</b> uses the most fuel. If one suddenly <b class='text-red-400'>shoots up</b>, that area had a bad blackout or is wasting fuel."
		}} />

		<!-- Avg Gen Hours by Sector -->
		<Chart option={lineChart(dates,
			sectors.map(s => ({
				name: s + ' (avg)',
				data: dates.map(d => {
					const sec = map.get(d)!.sectors.get(s);
					return sec && sec.n >= 2 ? Math.round(sec.h / sec.n * 10) / 10 : 0;
				}),
				color: sectorColors[s] || '#6b7280'
			})),
			{ title: 'Avg Generator Hours per Site per Day' }
		)} guide={{
			formula: "Total gen hours ÷ Number of sites = <b>Average hours per site</b>.",
			sources: [
				{ data: 'Generator Hours', file: 'Blackout Hr Excel', col: 'Gen Run Hr', method: 'SUM per sector' },
				{ data: 'Site Count', file: 'Blackout Hr Excel', col: 'sites with data', method: 'COUNT per sector' }
			],
			reading: [
				{ color: 'green', text: '✅ Low (2-4 hr) = Light blackout day' },
				{ color: 'amber', text: '⚠️ High (8+ hr) = Heavy blackout' },
				{ color: 'red', text: '🔴 12+ hr = Generators running almost all day' }
			],
			explain: "Shows how long <b>each site's generator ran on average</b>. Higher = worse blackouts in that area."
		}} />
	</div>

	<!-- ═══ CHAPTER 3: WHICH COST US ═══ -->
	{@const costs = costByDate(dates, map)}
	{@const sales = salesByDate()}
	{#if costs.some(c => c > 0)}
		<div id="ch-cost" class="scroll-mt-36">
			<div class="px-4 py-3 mb-3 mt-8" style="background: #383832; color: #feffd6;">
				<div class="flex items-center gap-3">
					<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">payments</span>
					<div>
						<div class="font-black uppercase text-sm">CHAPTER 3: WHICH COST US</div>
						<div class="text-[10px] opacity-75">Fuel burned → money spent. How much per day and per sector?</div>
					</div>
				</div>
				<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">
					? How much money went to diesel? Which sector is the most expensive to power?
				</div>
			</div>
		</div>
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
			<Chart option={lineChart(dates, sectors.map(s => ({ name: s, data: dates.map(d => { const sec = map.get(d)!.sectors.get(s); const price = priceOnDate(s, d); return sec ? Math.round((sec as any).l * price / 1e6 * 100) / 100 : 0; }), color: sectorColors[s] || '#6b7280' })), { title: 'Daily Diesel Cost (Million MMK) by Sector' })} guide={{ formula: "Liters × Price ÷ 1M = <b>Cost in Millions</b>.", sources: [{ data: 'Diesel Used', file: 'Blackout Hr Excel', col: 'Daily Used', method: 'SUM per sector' }, { data: 'Fuel Price', file: 'Daily Fuel Price', col: 'Price', method: 'LATEST' }], reading: [{ color: 'green', text: '✅ Flat = Budget on track' }, { color: 'red', text: '🔴 Rising = More blackouts or price hike' }], explain: "Total <b>money spent on diesel</b> per sector. Spikes = more blackouts or fuel price increase." }} />

			<Chart option={dualAxisChart(dates, dates.map(d => Math.round((sales.get(d) || 0) / 1e6 * 10) / 10), dates.map((_, i) => Math.round(costs[i] / 1e6 * 100) / 100), { title: 'Sales vs Diesel Cost (Millions)', barName: 'Sales (M)', lineName: 'Diesel (M)', barColor: '#3b82f6', lineColor: '#ef4444' })} guide={{ formula: "Blue bars = revenue. Red line = diesel cost. Gap = net benefit.", sources: [{ data: 'Sales', file: 'Sales Data', col: 'SALES_AMT', method: 'SUM/day' }, { data: 'Diesel Cost', file: 'Blackout+Price', col: 'L×Price', method: 'SUM/day' }], reading: [{ color: 'green', text: '✅ Big gap = Diesel is tiny vs sales' }, { color: 'red', text: '🔴 Lines close = Diesel eating revenue' }], explain: "Revenue vs fuel cost. The wider the gap, the healthier the business." }} />
		</div>
	{/if}

	<!-- ═══ CHAPTER 4: EATING INTO REVENUE ═══ -->
	{#if costs.some(c => c > 0)}
		<div id="ch-revenue" class="scroll-mt-36">
			<div class="px-4 py-3 mb-3 mt-8" style="background: #383832; color: #feffd6;">
				<div class="flex items-center gap-3">
					<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">trending_down</span>
					<div>
						<div class="font-black uppercase text-sm">CHAPTER 4: EATING INTO REVENUE</div>
						<div class="text-[10px] opacity-75">What % of sales goes to diesel? This decides if stores stay open or close.</div>
					</div>
				</div>
				<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">
					? Is diesel cost sustainable? Are we above the 3% threshold? Should any stores reduce hours?
				</div>
			</div>
		</div>
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
			<Chart option={lineChart(dates, [{ name: 'Diesel %', data: dates.map((d, i) => { const sv = sales.get(d) || 0; return sv > 0 ? Math.round(costs[i] / sv * 10000) / 100 : 0; }), color: '#ef4444' }], { title: 'Diesel % of Sales — The Decision Metric', markLines: [{ value: 3, label: '3% MONITOR', color: '#f97316' }, { value: 15, label: '15% REDUCE', color: '#dc2626' }] })} guide={{ formula: "(Diesel Cost ÷ Sales) × 100 = <b>Diesel %</b>.", sources: [{ data: 'Cost', file: 'Blackout+Price', col: 'L×Price', method: 'SUM' }, { data: 'Sales', file: 'Sales Data', col: 'SALES_AMT', method: 'SUM' }], reading: [{ color: 'green', text: '✅ Below 3% = OPEN — normal ops' }, { color: 'amber', text: '⚠️ 3-15% = MONITOR closely' }, { color: 'red', text: '🔴 Above 15% = REDUCE generator hours' }], explain: "The <b>key decision metric</b>. Below 3% = fine. Above 15% = cut hours. Above 60% = close store." }} />
		</div>
	{/if}

	<!-- ═══ CHAPTER 5: ARE WE PREPARED? ═══ -->
	<div id="ch-buffer" class="scroll-mt-36">
		<div class="px-4 py-3 mb-3 mt-8" style="background: #383832; color: #feffd6;">
			<div class="flex items-center gap-3">
				<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">battery_alert</span>
				<div>
					<div class="font-black uppercase text-sm">CHAPTER 5: ARE WE PREPARED?</div>
					<div class="text-[10px] opacity-75">How many days of fuel remaining? How many sites are in the danger zone?</div>
				</div>
			</div>
			<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">
				? Do we have enough fuel to survive? Which sites need urgent delivery?
			</div>
		</div>
	</div>
	<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
		<Chart option={lineChart(dates, sectors.map(s => ({ name: s, data: dates.map(d => { const sec = map.get(d)!.sectors.get(s); const tank = sec ? map.get(d)!.tank : 0; const burn = sec ? sec.l : 0; return burn > 0 ? Math.round(tank / burn * 10) / 10 : 0; }), color: sectorColors[s] || '#6b7280' })), { title: 'Buffer Days by Sector', markLines: [{ value: 7, label: 'Safe', color: '#16a34a' }, { value: 3, label: 'Critical', color: '#dc2626' }] })} guide={{ formula: "Tank ÷ Daily Burn = <b>Days left</b>.", sources: [{ data: 'Tank', file: 'Blackout Hr', col: 'Spare Tank', method: 'SUM/sector' }, { data: 'Burn', file: 'Blackout Hr', col: 'Daily Used', method: 'SUM/sector' }], reading: [{ color: 'green', text: '🟢 Above 7 = Safe' }, { color: 'amber', text: '🟡 3-7 = Plan delivery' }, { color: 'red', text: '🔴 Below 3 = Send fuel NOW' }], explain: "Like <b>phone battery %</b>. Below 3 days = red zone, charge immediately." }} />

		<Chart option={barChart(dates, dates.map(d => map.get(d)!.crit), { title: 'Critical Sites Count (< 3 days)', color: '#dc2626' })} guide={{ formula: "COUNT of sites with buffer < 3 days.", sources: [{ data: 'Buffer', file: 'Blackout Hr', col: 'Tank÷Used', method: 'COUNT <3' }], reading: [{ color: 'green', text: '✅ Zero = No emergencies' }, { color: 'red', text: '🔴 Rising = More sites running out' }], explain: "How many sites have their <b>fuel light on</b>. Zero is the goal." }} />
	</div>

	<!-- ═══ CHAPTER 6: ARE WE WASTING? ═══ -->
	<div id="ch-efficiency" class="scroll-mt-36">
		<div class="px-4 py-3 mb-3 mt-8" style="background: #383832; color: #feffd6;">
			<div class="flex items-center gap-3">
				<span class="material-symbols-outlined text-2xl" style="color: #ff9d00;">speed</span>
				<div>
					<div class="font-black uppercase text-sm">CHAPTER 6: ARE WE WASTING FUEL?</div>
					<div class="text-[10px] opacity-75">Efficiency detects if generators consume more than expected — theft, leaks, or bad maintenance.</div>
				</div>
			</div>
			<div class="mt-2 text-xs font-mono px-8" style="color: #00fc40;">
				? Is L/Hr normal? Which sector is least efficient? Any sudden spikes?
			</div>
		</div>
	</div>
	<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
		<Chart option={lineChart(dates, sectors.map(s => ({ name: s, data: dates.map(d => { const sec = map.get(d)!.sectors.get(s); return sec && sec.h > 10 && sec.n >= 2 ? Math.round(sec.l / sec.h * 10) / 10 : 0; }), color: sectorColors[s] || '#6b7280' })), { title: 'Efficiency — L/Hr by Sector' })} guide={{ formula: "Liters ÷ Gen Hours = <b>L/Hr</b>.", sources: [{ data: 'Used', file: 'Blackout Hr', col: 'Daily Used', method: 'SUM/sector' }, { data: 'Hours', file: 'Blackout Hr', col: 'Gen Run Hr', method: 'SUM/sector' }], reading: [{ color: 'green', text: '✅ Flat = Efficient' }, { color: 'red', text: '🔴 Rising = Waste or theft' }], explain: "Like <b>fuel economy</b>. Flat = healthy. Spike = investigate." }} />

		<Chart option={lineChart(dates, [{ name: 'L/Hr', data: dates.map(d => { const m = map.get(d)!; return m.hours > 0 ? Math.round(m.liters / m.hours * 10) / 10 : 0; }), color: '#8b5cf6' }], { title: 'Overall Efficiency — All Sites Combined' })} guide={{ formula: "Total diesel ÷ Total gen hours = <b>L/Hr</b>.", sources: [{ data: 'Used', file: 'Blackout Hr', col: 'Daily Used', method: 'SUM all' }, { data: 'Hours', file: 'Blackout Hr', col: 'Gen Run Hr', method: 'SUM all' }], reading: [{ color: 'green', text: '✅ 15-20 L/Hr = Normal' }, { color: 'red', text: '🔴 Above 25 = Investigate' }], explain: "Overall fleet efficiency. Sudden jumps = waste." }} />
	</div>

{/if}
