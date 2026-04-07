<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import Chart from '$lib/components/Chart.svelte';
	import { barChart, hbarChart, groupedBar } from '$lib/charts';

	let { dateFrom = '', dateTo = '', sector = '' }: { dateFrom?: string; dateTo?: string; sector?: string } = $props();

	let daily: any[] = $state([]);
	let fleet: any = $state({ dow_patterns: [], utilization: [], waste_scores: [] });
	let topGenHours: any[] = $state([]);
	let sectorHeatmap: any[] = $state([]);
	let loading = $state(true);

	async function load() {
		loading = true;
		const p = new URLSearchParams();
		if (dateFrom) p.set('date_from', dateFrom);
		if (dateTo) p.set('date_to', dateTo);
		if (sector) p.set('sector', sector);
		[daily, fleet, topGenHours, sectorHeatmap] = await Promise.all([
			api.get(`/daily-summary?${p}`),
			api.get(`/operations/fleet-stats?${p}`),
			api.get(`/rankings/gen_hours?${p}&limit=15`).catch(() => []),
			api.get(`/sector-heatmap?${p}`).catch(() => []),
		]);
		loading = false;
	}

	onMount(load);

	// ---------- LAST DAY BREAKDOWN ----------
	function lastDayData() {
		if (!daily.length) return null;
		const maxDate = daily.reduce((m: string, r: any) => r.date > m ? r.date : m, '');
		const rows = daily.filter((r: any) => r.date === maxDate);
		if (!rows.length) return null;

		// #33 Top Sites by Fuel Used
		const byFuel = [...rows].sort((a: any, b: any) => (b.total_daily_used || 0) - (a.total_daily_used || 0)).slice(0, 15);
		const fuelChart = hbarChart(
			byFuel.map((r: any) => r.site_id),
			byFuel.map((r: any) => Math.round(r.total_daily_used || 0)),
			{ title: 'TOP SITES BY FUEL USED — LAST DAY', colors: byFuel.map((r: any) => (r.total_daily_used || 0) > 100 ? '#be2d06' : '#007518') }
		);

		// #34 Gen Hours by Site
		const byGen = [...rows].sort((a: any, b: any) => (b.total_gen_run_hr || 0) - (a.total_gen_run_hr || 0)).slice(0, 15);
		const genChart = hbarChart(
			byGen.map((r: any) => r.site_id),
			byGen.map((r: any) => Math.round((r.total_gen_run_hr || 0) * 10) / 10),
			{ title: 'GEN HOURS BY SITE — LAST DAY', colors: byGen.map((r: any) => (r.total_gen_run_hr || 0) > 12 ? '#be2d06' : '#006f7c') }
		);

		// #35 Efficiency L/Hr by Site
		const withEff = rows
			.filter((r: any) => (r.total_gen_run_hr || 0) > 0)
			.map((r: any) => ({ ...r, eff: (r.total_daily_used || 0) / (r.total_gen_run_hr || 1) }))
			.sort((a: any, b: any) => b.eff - a.eff)
			.slice(0, 15);
		const effChart = hbarChart(
			withEff.map((r: any) => r.site_id),
			withEff.map((r: any) => Math.round(r.eff * 10) / 10),
			{ title: 'EFFICIENCY L/HR BY SITE — LAST DAY', colors: withEff.map((r: any) => r.eff > 30 ? '#be2d06' : r.eff > 20 ? '#ff9d00' : '#007518') }
		);

		return { maxDate, fuelChart, genChart, effChart, fuelCount: byFuel.length, genCount: byGen.length, effCount: withEff.length };
	}

	// Week-over-Week
	function wow() {
		if (!daily.length) return null;
		const dates = [...new Set(daily.map((r: any) => r.date))].sort();
		if (dates.length < 8) return null;
		const mid = dates.length - 7;
		const tw = daily.filter((r: any) => dates.indexOf(r.date) >= mid);
		const lw = daily.filter((r: any) => dates.indexOf(r.date) >= mid - 7 && dates.indexOf(r.date) < mid);
		const sum = (arr: any[], key: string) => arr.reduce((s: number, r: any) => s + (r[key] || 0), 0);
		const twFuel = sum(tw, 'total_daily_used'), lwFuel = sum(lw, 'total_daily_used');
		const twHrs = sum(tw, 'total_gen_run_hr'), lwHrs = sum(lw, 'total_gen_run_hr');
		const twTank = sum(tw, 'spare_tank_balance'), lwTank = sum(lw, 'spare_tank_balance');
		const twBurn = twFuel / 7, lwBurn = lwFuel / 7;
		const twBuf = twBurn > 0 ? twTank / twBurn : 0, lwBuf = lwBurn > 0 ? lwTank / lwBurn : 0;
		return [
			{ label: 'Fuel (L)', tw: twFuel, lw: lwFuel, good: 'low' },
			{ label: 'Gen Hours', tw: twHrs, lw: lwHrs, good: 'low' },
			{ label: 'Buffer Days', tw: twBuf, lw: lwBuf, good: 'high' },
			{ label: 'Burn/Day', tw: twBurn, lw: lwBurn, good: 'low' },
		];
	}

	function pct(tw: number, lw: number) { return lw > 0 ? ((tw - lw) / lw * 100) : 0; }
	function arrow(v: number) { return v > 0 ? '▲' : v < 0 ? '▼' : '→'; }
	function wowColor(v: number, good: string) {
		if (good === 'low') return v > 5 ? 'color: #be2d06' : v < -5 ? 'color: #007518' : 'color: #ff9d00';
		return v > 5 ? 'color: #007518' : v < -5 ? 'color: #be2d06' : 'color: #ff9d00';
	}
	function fmt(v: number) { return v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(1)+'K' : v.toFixed(v < 10 ? 1 : 0); }

	// Day of Week
	function dowData() {
		const days = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
		const buckets: Record<string, { fuel: number[]; hours: number[] }> = {};
		days.forEach(d => buckets[d] = { fuel: [], hours: [] });
		for (const r of daily) {
			const dow = new Date(r.date).getDay();
			const name = days[dow];
			buckets[name].fuel.push(r.total_daily_used || 0);
			buckets[name].hours.push(r.total_gen_run_hr || 0);
		}
		const order = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
		const avgFuel = order.map(d => { const a = buckets[d].fuel; return a.length ? Math.round(a.reduce((s,v) => s+v, 0) / a.length) : 0; });
		const avgHrs = order.map(d => { const a = buckets[d].hours; return a.length ? Math.round(a.reduce((s,v) => s+v, 0) / a.length * 10) / 10 : 0; });
		return { order, avgFuel, avgHrs };
	}

	// Recommendations
	function recs() {
		const r: { icon: string; color: string; text: string }[] = [];
		const crit = daily.filter((d: any) => (d.days_of_buffer || 99) < 3);
		if (crit.length > 0) {
			const sites = [...new Set(crit.map((c: any) => c.site_id))].slice(0, 5);
			r.push({ icon: '🔴', color: 'border-color: #be2d06', text: `${sites.length} sites have < 3 days diesel — send fuel: ${sites.join(', ')}` });
		}
		return r;
	}
</script>

{#if loading}
	<div class="space-y-4 py-4">
		<div class="skeleton h-5 w-48"></div>
		<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
			<div class="skeleton h-[280px]"></div>
			<div class="skeleton h-[280px]"></div>
			<div class="skeleton h-[280px]"></div>
		</div>
		<div class="skeleton h-5 w-36 mt-4"></div>
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
			<div class="skeleton h-[260px]"></div>
			<div class="skeleton h-[260px]"></div>
		</div>
	</div>
{:else if daily.length > 0}
	<!-- Last Day Breakdown -->
	{@const ld = lastDayData()}
	{#if ld}
		<details class="mb-6">
			<summary class="cursor-pointer text-sm font-black uppercase px-4 py-2.5" style="background: #383832; color: #feffd6;">LAST DAY BREAKDOWN — {ld.maxDate}</summary>
			<div class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-3">
				<!-- #33 Top Sites by Fuel Used -->
				<Chart option={ld.fuelChart} height="{Math.max(280, ld.fuelCount * 26)}px" guide={{ formula: 'total_daily_used for each site on the latest date, sorted descending, top 15.', sources: [{ data: 'Daily Used', file: 'Blackout Hr Excel', col: 'Daily Used', method: 'Filter max date, sort DESC' }], reading: [{ color: 'red', text: 'Long red bar = Heavy fuel consumer on this day' }, { color: 'green', text: 'Short green bar = Low fuel usage' }], explain: 'Shows which sites <b>burned the most fuel yesterday</b>. Target the top bars for efficiency audits.' }} />

				<!-- #34 Gen Hours by Site -->
				<Chart option={ld.genChart} height="{Math.max(280, ld.genCount * 26)}px" guide={{ formula: 'total_gen_run_hr for each site on the latest date, sorted descending, top 15.', sources: [{ data: 'Gen Hours', file: 'Blackout Hr Excel', col: 'Gen Run Hr', method: 'Filter max date, sort DESC' }], reading: [{ color: 'red', text: 'Long red bar = Generator ran 12+ hours' }, { color: 'green', text: 'Teal bar = Moderate generator usage' }], explain: 'Shows which sites had the <b>longest generator run time yesterday</b>. Long bars mean severe blackouts at that site.' }} />

				<!-- #35 Efficiency L/Hr by Site -->
				<Chart option={ld.effChart} height="{Math.max(280, ld.effCount * 26)}px" guide={{ formula: 'total_daily_used ÷ total_gen_run_hr for each site on the latest date (sites with gen hours > 0).', sources: [{ data: 'Efficiency', file: 'Blackout Hr Excel', col: 'Daily Used ÷ Gen Run Hr', method: 'Compute ratio, sort DESC' }], reading: [{ color: 'red', text: 'Red bar > 30 L/Hr = Possible waste or theft' }, { color: 'amber', text: 'Amber 20-30 L/Hr = Monitor closely' }, { color: 'green', text: 'Green < 20 L/Hr = Normal range' }], explain: 'How many <b>liters each generator burns per hour</b>. Compare against the rated spec — high values mean fuel is being wasted.' }} />
			</div>
		</details>
	{/if}

	<!-- Week over Week -->
	{@const w = wow()}
	{#if w}
		<div style="background: #383832; color: #feffd6;" class="px-4 py-2.5 font-black text-sm uppercase mt-6">📅 WEEK OVER WEEK</div>
		<div class="flex flex-wrap gap-2 p-3 mb-6" style="background: #f6f4e9; border: 1px solid #383832; border-top: 0;">
			{#each w as m}
				{@const p = pct(m.tw, m.lw)}
				<div class="flex-1 min-w-[130px] p-3 text-center" style="background: white; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
					<div class="text-xs mb-1" style="color: #65655e;">{m.label}</div>
					<div class="text-xl font-extrabold" style="{wowColor(p, m.good)}">{arrow(p)} {Math.abs(p).toFixed(0)}%</div>
					<div class="text-[11px] mt-1" style="color: #65655e;">{fmt(m.tw)} vs {fmt(m.lw)}</div>
				</div>
			{/each}
		</div>
	{/if}

	<!-- Day of Week -->
	{@const dow = dowData()}
	<details class="mb-6">
		<summary class="cursor-pointer text-sm font-black uppercase px-4 py-2.5" style="background: #383832; color: #feffd6;">📅 Day-of-Week Patterns</summary>
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">
			<Chart option={barChart(dow.order, dow.avgFuel, { title: 'Avg Fuel Used (L) by Day', color: '#be2d06' })} height="280px" guide={{ formula: 'Average daily fuel (liters) grouped by day of week.', sources: [{ data: 'Fuel Used', file: 'Blackout Hr Excel', col: 'Daily Used', method: 'AVG per DOW' }], reading: [{ color: 'green', text: '✅ Even bars = Consistent fuel use' }, { color: 'red', text: '🔴 Spike on a day = Pattern worth investigating' }], explain: 'Like checking which day you <b>spend the most on gas</b>. Spikes reveal weekly patterns.' }} />
			<Chart option={barChart(dow.order, dow.avgHrs, { title: 'Avg Gen Hours by Day', color: '#006f7c' })} height="280px" guide={{ formula: 'Average generator run hours grouped by day of week.', sources: [{ data: 'Gen Hours', file: 'Blackout Hr Excel', col: 'Gen Run Hr', method: 'AVG per DOW' }], reading: [{ color: 'green', text: '✅ Even bars = Consistent blackout pattern' }, { color: 'red', text: '🔴 Tall bar = Worst blackout day' }], explain: 'Shows which days have the <b>longest blackouts</b>. Plan staffing and fuel deliveries around peaks.' }} />
		</div>
	</details>

	<!-- Recommendations -->
	{@const rc = recs()}
	{#if rc.length > 0}
		<div class="p-4 mb-6" style="background: white; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
			<div class="font-black text-sm uppercase mb-2" style="color: #383832;">RECOMMENDATIONS</div>
			{#each rc as r}
				<div class="border-l-4 pl-3 py-1 text-sm mb-1" style="border-color: #be2d06; color: #383832;">{r.icon} {r.text}</div>
			{/each}
		</div>
	{/if}

	<!-- Fleet Stats -->
	{#if fleet.dow_patterns.length > 0}
		{@const dowDays = fleet.dow_patterns.map((d: any) => d.dow)}
		<details class="mb-6">
			<summary class="cursor-pointer text-sm font-black uppercase px-4 py-2.5" style="background: #383832; color: #feffd6;">⚙️ Operations & Fleet</summary>
			<div class="mt-3 space-y-4">
				<!-- DOW patterns: Gen Hours + Blackout -->
				<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
					<Chart option={barChart(dowDays, fleet.dow_patterns.map((d: any) => Math.round(d.avg_fuel || 0)), { title: 'Avg Fuel by Day of Week', color: '#be2d06' })} height="260px" guide={{ formula: 'Average fuel liters per day-of-week across all sites.', sources: [{ data: 'Fuel', file: 'Blackout Hr Excel', col: 'Daily Used', method: 'AVG per DOW' }], reading: [{ color: 'green', text: '✅ Even bars = Consistent' }, { color: 'red', text: '🔴 Spike = High-burn day' }], explain: 'Shows <b>which days burn the most fuel</b>. Plan deliveries before peak days.' }} />
					<Chart option={barChart(dowDays, fleet.dow_patterns.map((d: any) => Math.round((d.avg_gen_hr || 0) * 10) / 10), { title: 'Avg Gen Hours by Day of Week', color: '#006f7c' })} height="260px" guide={{ formula: 'Average generator run hours per day-of-week.', sources: [{ data: 'Gen Hours', file: 'Blackout Hr Excel', col: 'Gen Run Hr', method: 'AVG per DOW' }], reading: [{ color: 'green', text: '✅ Even = Predictable schedule' }, { color: 'red', text: '🔴 Spike = Worst blackout day' }], explain: 'Like knowing <b>traffic is worst on Fridays</b> — plan generator maintenance around low days.' }} />
					<Chart option={barChart(dowDays, fleet.dow_patterns.map((d: any) => Math.round((d.avg_blackout || 0) * 10) / 10), { title: 'Avg Blackout Hr by Day of Week', color: '#ff9d00' })} height="260px" guide={{ formula: 'Average blackout hours per day-of-week.', sources: [{ data: 'Blackout', file: 'Blackout Hr Excel', col: 'Blackout Hr', method: 'AVG per DOW' }], reading: [{ color: 'green', text: '✅ Low bars = Good grid days' }, { color: 'red', text: '🔴 Tall bar = Worst power day' }], explain: 'Reveals <b>weekly power grid patterns</b>. Schedule critical operations on low-blackout days.' }} />
				</div>

				<!-- Generator Utilization -->
				{#if fleet.utilization.length > 0}
					<Chart option={hbarChart(
						fleet.utilization.map((u: any) => `${u.site_id} ${u.model_name || ''}`),
						fleet.utilization.map((u: any) => u.utilization_pct || 0),
						{ title: 'Generator Utilization %', colors: fleet.utilization.map((u: any) => (u.utilization_pct || 0) > 80 ? '#be2d06' : (u.utilization_pct || 0) > 50 ? '#ff9d00' : '#007518') }
					)} height="{Math.max(300, fleet.utilization.length * 24)}px" guide={{ formula: 'Active days ÷ Total reporting days × 100 = <b>utilization %</b>.', sources: [{ data: 'Gen Run Hours', file: 'Blackout Hr Excel', col: 'Gen Run Hr', method: 'COUNT days > 0' }], reading: [{ color: 'red', text: '🔴 > 80% = Running almost daily — heavy blackout area' }, { color: 'green', text: '🟢 < 30% = Generator rarely needed' }], explain: 'Shows how often each generator <b>actually runs</b>. High % = frequent blackouts in that area.' }} />
				{/if}

				<!-- Waste/Theft Scores -->
				{#if fleet.waste_scores.length > 0}
					<Chart option={hbarChart(
						fleet.waste_scores.map((w: any) => w.site_id),
						fleet.waste_scores.map((w: any) => w.waste_score || 0),
						{ title: 'Theft/Waste Probability Score', colors: fleet.waste_scores.map((w: any) => (w.waste_score || 0) > 30 ? '#be2d06' : (w.waste_score || 0) > 15 ? '#ff9d00' : '#007518') }
					)} height="{Math.max(200, fleet.waste_scores.length * 28)}px" guide={{ formula: '(Actual L/Hr ÷ Rated L/Hr − 1) × 100 = <b>waste score %</b>. Only sites with 3+ data points.', sources: [{ data: 'Efficiency', file: 'Blackout Hr Excel', col: 'Daily Used ÷ Gen Run Hr', method: 'AVG vs rated' }], reading: [{ color: 'red', text: '🔴 > 30% = Likely theft or major leak' }, { color: 'amber', text: '🟡 15-30% = Investigate maintenance' }, { color: 'green', text: '🟢 < 15% = Normal variation' }], explain: 'Compares <b>actual vs expected</b> fuel burn. A generator rated 20L/Hr burning 30L/Hr scores 50% — something is wrong.' }} />
				{/if}
			</div>
		</details>
	{/if}

	<!-- #59 Top 15 Sites by Gen Run Hours -->
	{#if topGenHours.length > 0}
		<Chart option={hbarChart(
			topGenHours.map((s: any) => s.site_id),
			topGenHours.map((s: any) => Math.round(s.gen_hours || s.total_gen_hr || 0)),
			{ title: 'Top 15 Sites by Gen Run Hours', colors: topGenHours.map((s: any) => (s.gen_hours || s.total_gen_hr || 0) > 100 ? '#be2d06' : '#006f7c') }
		)} height="{Math.max(300, topGenHours.length * 28)}px" guide={{ formula: 'SUM of generator run hours per site. Higher = more blackout exposure.', sources: [{ data: 'Gen Hours', file: 'Blackout Hr Excel', col: 'Gen Run Hr', method: 'SUM per site' }], reading: [{ color: 'red', text: '🔴 Top bars = Most blackout-affected sites' }, { color: 'green', text: '🟢 Short bars = Light blackout exposure' }], explain: 'Sites with the <b>most generator hours</b> suffer the worst blackouts. These are the priority for fuel delivery.' }} />
	{/if}

	<!-- #39 Sector Comparison Scorecard -->
	{#if sectorHeatmap.length > 1}
		{@const metrics = ['Buffer', 'Efficiency', 'Low Fuel', 'Low Blackout', 'Low Diesel%']}
		{@const sColors: Record<string, string> = { CMHL: '#FF9800', CP: '#2196F3', CFC: '#4CAF50', PG: '#9C27B0' }}
		{@const maxBuf = Math.max(...sectorHeatmap.map((s: any) => s.buffer_days || 0), 1)}
		{@const maxEff = Math.max(...sectorHeatmap.map((s: any) => s.avg_fuel > 0 && s.avg_gen_hr > 0 ? s.avg_fuel / s.avg_gen_hr : 0), 1)}
		{@const maxFuel = Math.max(...sectorHeatmap.map((s: any) => s.avg_fuel || 0), 1)}
		{@const maxBO = Math.max(...sectorHeatmap.map((s: any) => s.blackout_hr || 0), 1)}
		{@const maxDP = Math.max(...sectorHeatmap.map((s: any) => s.diesel_pct || 0), 1)}
		<Chart option={groupedBar(metrics,
			sectorHeatmap.map((s: any) => ({
				name: s.sector_id,
				data: [
					Math.round((s.buffer_days || 0) / maxBuf * 100),
					Math.round((1 - (s.avg_fuel > 0 && s.avg_gen_hr > 0 ? (s.avg_fuel / s.avg_gen_hr) / maxEff : 0)) * 100),
					Math.round((1 - (s.avg_fuel || 0) / maxFuel) * 100),
					Math.round((1 - (s.blackout_hr || 0) / maxBO) * 100),
					Math.round((1 - (s.diesel_pct || 0) / maxDP) * 100),
				],
				color: sColors[s.sector_id] || '#6b7280'
			})),
			{ title: 'Sector Scores (0-100, higher = better)' }
		)} guide={{ formula: 'Each metric normalized 0-100. Buffer: higher = more fuel. Others: lower raw value = higher score (inverted).', sources: [{ data: 'All Metrics', file: 'All Sources', col: 'Buffer/Efficiency/Fuel/Blackout/Diesel%', method: 'Normalized 0-100' }], reading: [{ color: 'green', text: '✅ Tall bars = Good performance in that metric' }, { color: 'red', text: '🔴 Short bars = Weak area to improve' }], explain: 'Like a <b>school report card</b> for each sector. Higher bar = better grade. Find which sectors need help in which areas.' }} />
	{/if}
{/if}
