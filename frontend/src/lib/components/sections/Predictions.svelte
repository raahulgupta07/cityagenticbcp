<script lang="ts">
	import { onMount } from 'svelte';
	import { api, downloadExcel } from '$lib/api';
	import Chart from '$lib/components/Chart.svelte';
	import { lineChart, hbarChart, dualAxisChart } from '$lib/charts';

	let { sector = '', dateFrom = '', dateTo = '' }: { sector?: string; dateFrom?: string; dateTo?: string } = $props();

	let loading = $state(true);
	let predictions: any = $state(null);
	let fuelFc: any = $state(null);
	let dailySummary: any[] = $state([]);
	let generatorRisk: any[] = $state([]);
	let operatingModes: any[] = $state([]);
	let breakEven: any[] = $state([]);
	let anomalies: any[] = $state([]);
	let deliveryQueue: any[] = $state([]);
	let fuelIntel: any = $state(null);

	async function load() {
		loading = true;
		try {
			[predictions, fuelFc, dailySummary, generatorRisk, operatingModes, breakEven, anomalies, deliveryQueue, fuelIntel] = await Promise.all([
				api.get('/predictions/all'),
				api.get('/fuel-forecast'),
				api.get('/daily-summary').catch(() => []),
				api.get('/generator-risk').catch(() => []),
				api.get('/operating-modes').catch(() => []),
				api.get('/break-even').catch(() => []),
				api.get('/anomalies').catch(() => []),
				api.get('/delivery-queue').catch(() => []),
				api.get('/fuel-intel').catch(() => null),
			]);
		} catch (e) { console.error(e); }
		loading = false;
	}

	onMount(load);

	function forecastChart(data: any[], title: string, color: string) {
		if (!data || data.length === 0) return null;
		const dates = data.map((r: any) => r.date);
		return lineChart(dates, [
			{ name: 'Forecast', data: data.map((r: any) => Math.round(r.value)), color },
			{ name: 'Lower', data: data.map((r: any) => Math.round(r.lower)), color: '#4b5563' },
			{ name: 'Upper', data: data.map((r: any) => Math.round(r.upper)), color: '#4b5563' },
		], { title });
	}
</script>

{#if loading}
	<p class="text-sm py-4 text-center" style="color: #65655e;">Loading predictions...</p>
{:else}
	<h2 class="text-lg font-black uppercase mt-6 mb-3 px-3 py-1" style="background: #383832; color: #feffd6;">PREDICTIONS & FORECASTS</h2>

	<!-- Stockout Forecast -->
	{#if predictions?.stockout?.length > 0}
		<h3 class="text-sm font-black uppercase mb-2 px-3 py-1" style="background: #383832; color: #feffd6;">BUFFER DEPLETION TIMELINE</h3>
		{@const sorted = predictions.stockout.sort((a: any, b: any) => (a.days_until_stockout || 99) - (b.days_until_stockout || 99)).slice(0, 15)}
		<Chart option={hbarChart(
			sorted.map((r: any) => r.site_id),
			sorted.map((r: any) => Math.round((r.days_until_stockout || 0) * 10) / 10),
			{ title: 'Sites Running Out Soonest (days)', colors: sorted.map((r: any) => (r.days_until_stockout || 0) < 3 ? '#ef4444' : (r.days_until_stockout || 0) < 7 ? '#f59e0b' : '#22c55e') }
		)} height="{Math.max(300, sorted.length * 28)}px" guide={{ formula: "Buffer depletion = current tank balance / average daily consumption. Shows <b>days until fuel runs out</b>.", sources: [{ data: 'Buffer Days', file: 'Blackout Hr Excel', col: 'Tank / Daily Used', method: 'Exponential smoothing' }], reading: [{ color: 'red', text: 'Short bar (< 3 days) = Send fuel NOW' }, { color: 'amber', text: '3-7 days = Plan delivery' }, { color: 'green', text: '7+ days = Safe' }], explain: "Countdown timer for each site's fuel tank. Red sites will run dry first — dispatch fuel there." }} />
	{:else}
		<p class="text-sm mb-4" style="color: #383832;">No sites projected to run out within 7 days.</p>
	{/if}

	<!-- Fuel Price Forecast -->
	{#if fuelFc && fuelFc.history?.length > 0}
		<h3 class="text-sm font-black uppercase mt-4 mb-2 px-3 py-1" style="background: #383832; color: #feffd6;">FUEL PRICE FORECAST (7-DAY)</h3>
		{@const hist = fuelFc.history}
		{@const fc = fuelFc.forecast || []}
		{@const allDates = [...hist.map((r: any) => r.date), ...fc.map((r: any) => r.date)]}
		{@const histVals = [...hist.map((r: any) => Math.round(r.price || 0)), ...fc.map(() => 0)]}
		{@const predVals = [...hist.map(() => 0), ...fc.map((r: any) => Math.round(r.predicted_price || 0))]}
		<Chart option={lineChart(allDates, [
			{ name: 'Historical', data: histVals, color: '#3b82f6' },
			{ name: 'Forecast', data: predVals, color: '#ef4444' }
		], { title: `Price Trend: ${(fuelFc.trend || 'stable').toUpperCase()}, R²: ${(fuelFc.r_squared || 0).toFixed(2)}` })} guide={{ formula: "Ridge regression with polynomial features predicts next 7 days of fuel prices.", sources: [{ data: 'Fuel Price', file: 'Daily Fuel Price Excel', col: 'Price/L', method: 'Ridge regression' }], reading: [{ color: 'blue', text: 'Blue = Actual historical prices' }, { color: 'red', text: 'Red = ML prediction (7-day)' }, { color: 'green', text: 'R-squared closer to 1.0 = More reliable' }], explain: "Uses <b>machine learning</b> to predict diesel prices based on past patterns. R-squared tells you how good the prediction is." }} />
	{/if}

	<!-- 7-Day Forecasts Grid -->
	{#if predictions}
		{@const charts = [
			{ key: 'fuel_forecast', title: '7-Day Fuel Consumption Forecast (L)', color: '#ef4444' },
			{ key: 'efficiency_forecast', title: '7-Day Efficiency Forecast (L/Hr)', color: '#8b5cf6' },
			{ key: 'buffer_forecast', title: '7-Day Buffer Days Forecast', color: '#3b82f6' },
			{ key: 'gen_hr_forecast', title: '7-Day Gen Hours Forecast', color: '#06b6d4' },
			{ key: 'cost_forecast', title: '7-Day Diesel Cost Forecast (MMK)', color: '#f59e0b' },
			{ key: 'blackout_forecast', title: '7-Day Blackout Hours Forecast', color: '#ec4899' },
		]}
		{@const hasForecasts = charts.some(c => predictions[c.key]?.length > 0)}

		{#if hasForecasts}
			<h3 class="text-sm font-black uppercase mt-6 mb-2 px-3 py-1" style="background: #383832; color: #feffd6;">7-DAY FORECASTS</h3>
			<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
				{#each charts as c}
					{@const opt = forecastChart(predictions[c.key], c.title, c.color)}
					{#if opt}
						<Chart option={opt} height="280px" guide={{ formula: "Exponential smoothing with trend extrapolation. Central line = forecast, gray = confidence band.", sources: [{ data: 'Daily Aggregates', file: 'Blackout Hr Excel', col: 'Various', method: 'Exponential smoothing' }], reading: [{ color: 'green', text: 'Flat trend = Stable operations' }, { color: 'red', text: 'Rising line = Budget pressure ahead' }], explain: "Predicts <b>next 7 days</b> based on recent trends. Gray bands show uncertainty range." }} />
					{/if}
				{/each}
			</div>
		{/if}

		<!-- Purchase Volume by Supplier -->
		{#if predictions.purchase_volume?.length > 0}
			<h3 class="text-sm font-black uppercase mt-6 mb-2 px-3 py-1" style="background: #383832; color: #feffd6;">PURCHASE VOLUME BY SUPPLIER</h3>
			<Chart option={hbarChart(
				predictions.purchase_volume.map((r: any) => `${r.supplier} (avg ${Math.round(r.avg_price || 0)} MMK/L)`),
				predictions.purchase_volume.map((r: any) => Math.round(r.total_liters || 0)),
				{ title: 'Total Liters Purchased', colors: predictions.purchase_volume.map((_: any, i: number) => i === 0 ? '#3b82f6' : '#8b5cf6') }
			)} height="{Math.max(200, predictions.purchase_volume.length * 40)}px" guide={{ formula: "Total liters purchased from each supplier, with average price per liter shown.", sources: [{ data: 'Purchase Volume', file: 'fuel_purchases table', col: 'qty_l, price_per_l', method: 'SUM per supplier' }], reading: [{ color: 'blue', text: 'Longer bar = More volume from that supplier' }, { color: 'amber', text: 'Compare avg price in label to find cheapest' }], explain: "Shows which suppliers you buy the most from and at what average price. Use this to negotiate better rates." }} />
		{/if}
	{/if}

	<!-- #81 Sales vs Blackout Hours (Dual Axis) -->
	{#if dailySummary?.length > 0}
		<div style="background: #383832; color: #feffd6;" class="px-4 py-2.5 font-black text-sm uppercase mt-6">SALES VS BLACKOUT HOURS</div>
		{@const dsData = dailySummary.slice(-30)}
		<Chart option={dualAxisChart(
			dsData.map((r: any) => r.date || ''),
			dsData.map((r: any) => Math.round((r.sales || 0) / 1e6 * 10) / 10),
			dsData.map((r: any) => Math.round((r.blackout_hr || 0) * 10) / 10),
			{ title: 'Daily Sales (M) vs Blackout Hours', barName: 'Sales (M)', lineName: 'Blackout Hr', barColor: '#3b82f6', lineColor: '#ef4444' }
		)} guide={{ formula: "Bars = total daily sales (millions). Line = total blackout hours per day. Shows revenue impact of power outages.", sources: [{ data: 'Sales & Blackout', file: 'daily_summary API', col: 'sales, blackout_hr', method: 'Daily totals' }], reading: [{ color: 'blue', text: 'Tall blue bar = High sales day' }, { color: 'red', text: 'Red line spike = More blackouts — check if sales dipped' }], explain: "Compares <b>money earned</b> against <b>hours without power</b>. When the red line goes up and blue bars go down, blackouts are hurting revenue." }} />
	{/if}

	<!-- #87 At-Risk Generators Table -->
	{#if generatorRisk?.length > 0}
		<div style="background: #383832; color: #feffd6;" class="px-4 py-2.5 font-black text-sm uppercase mt-6">AT-RISK GENERATORS</div>
		<div style="border: 2px solid #383832; background: white;">
			<div class="px-4 py-2 flex justify-between" style="background: #383832; color: #feffd6;">
				<span class="font-bold uppercase text-sm">Generator Risk Assessment</span>
				<button onclick={() => downloadExcel(generatorRisk, 'At-Risk Generators')}
					class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
					style="color: #00fc40;">
					<span class="material-symbols-outlined text-sm">download</span> EXCEL
				</button>
			</div>
			<div class="overflow-x-auto">
				<table class="w-full text-xs">
					<thead><tr style="background: #ebe8dd;">
						<th class="py-2 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">Site</th>
						<th class="py-2 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">Site_Code</th>
						<th class="py-2 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">Generator</th>
						<th class="py-2 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">Risk Level</th>
						<th class="py-2 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">Run Hours</th>
						<th class="py-2 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">Last Maintenance</th>
					</tr></thead>
					<tbody>
						{#each generatorRisk as row, i}
							<tr style="background: {i % 2 ? '#f6f4e9' : 'white'}; border-bottom: 1px solid #ebe8dd;">
								<td class="py-2 px-3">{row.site_id || row.site || '-'}</td>
								<td class="py-2 px-3 font-mono text-xs">{row.site_code || row.region || ''}</td>
								<td class="py-2 px-3">{row.generator_id || row.generator || '-'}</td>
								<td class="py-2 px-3">
									<span class="px-2 py-0.5 rounded text-white text-xs font-bold" style="background: {(row.risk_level || row.risk || '').toLowerCase() === 'high' ? '#ef4444' : (row.risk_level || row.risk || '').toLowerCase() === 'medium' ? '#f59e0b' : '#22c55e'};">
										{row.risk_level || row.risk || '-'}
									</span>
								</td>
								<td class="py-2 px-3">{Math.round(row.run_hours || 0).toLocaleString()}</td>
								<td class="py-2 px-3">{row.last_maintenance || '-'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}

	<!-- #88 Operating Mode KPI Cards -->
	{#if operatingModes?.length > 0}
		<div style="background: #383832; color: #feffd6;" class="px-4 py-2.5 font-black text-sm uppercase mt-6">OPERATING MODE DISTRIBUTION</div>
		{@const modeCounts = { OPEN: 0, MONITOR: 0, REDUCE: 0, CLOSE: 0 }}
		{@const _modeCalc = operatingModes.forEach((r: any) => {
			const m = (r.mode || r.operating_mode || '').toUpperCase();
			if (m in modeCounts) (modeCounts as any)[m]++;
		})}
		<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
			<div class="rounded-lg p-4 text-center" style="background: #22c55e; color: white;">
				<div class="text-xs font-bold uppercase opacity-80">OPEN</div>
				<div class="text-2xl font-black">{modeCounts.OPEN}</div>
				<div class="text-xs opacity-80">sites</div>
			</div>
			<div class="rounded-lg p-4 text-center" style="background: #3b82f6; color: white;">
				<div class="text-xs font-bold uppercase opacity-80">MONITOR</div>
				<div class="text-2xl font-black">{modeCounts.MONITOR}</div>
				<div class="text-xs opacity-80">sites</div>
			</div>
			<div class="rounded-lg p-4 text-center" style="background: #f59e0b; color: white;">
				<div class="text-xs font-bold uppercase opacity-80">REDUCE</div>
				<div class="text-2xl font-black">{modeCounts.REDUCE}</div>
				<div class="text-xs opacity-80">sites</div>
			</div>
			<div class="rounded-lg p-4 text-center" style="background: #ef4444; color: white;">
				<div class="text-xs font-bold uppercase opacity-80">CLOSE</div>
				<div class="text-2xl font-black">{modeCounts.CLOSE}</div>
				<div class="text-xs opacity-80">sites</div>
			</div>
		</div>
	{/if}

	<!-- #89 Recommend CLOSE Table -->
	{#if breakEven?.length > 0}
		{@const closeSites = breakEven.filter((r: any) => (r.recommendation || '').toUpperCase() === 'CLOSE' || (r.diesel_pct || 0) > 30)}
		{#if closeSites.length > 0}
			<div style="background: #383832; color: #feffd6;" class="px-4 py-2.5 font-black text-sm uppercase mt-6">RECOMMENDED CLOSURES</div>
			<div style="border: 2px solid #383832; background: white;">
				<div class="px-4 py-2 flex justify-between" style="background: #383832; color: #feffd6;">
					<span class="font-bold uppercase text-sm">Sites Recommended to Close (Diesel% &gt; 30% or Break-Even Fail)</span>
					<button onclick={() => downloadExcel(closeSites, 'Recommend Close', { statusColumns: ['recommendation'] })}
						class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
						style="color: #00fc40;">
						<span class="material-symbols-outlined text-sm">download</span> EXCEL
					</button>
				</div>
				<div class="overflow-x-auto">
					<table class="w-full text-xs">
						<thead><tr style="background: #ebe8dd;">
							<th class="py-2 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">Site</th>
							<th class="py-2 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">Diesel/Day</th>
							<th class="py-2 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">Sales</th>
							<th class="py-2 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">Diesel%</th>
							<th class="py-2 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">Action</th>
						</tr></thead>
						<tbody>
							{#each closeSites as row, i}
								<tr style="background: {i % 2 ? '#f6f4e9' : 'white'}; border-bottom: 1px solid #ebe8dd;">
									<td class="py-2 px-3 font-bold">{row.site_id || row.site || '-'}</td>
									<td class="py-2 px-3">{Math.round(row.diesel_per_day || row.diesel_daily || 0).toLocaleString()} L</td>
									<td class="py-2 px-3">{Math.round((row.sales || 0) / 1e6 * 10) / 10}M</td>
									<td class="py-2 px-3">
										<span class="px-2 py-0.5 rounded text-white text-xs font-bold" style="background: {(row.diesel_pct || 0) > 30 ? '#ef4444' : '#f59e0b'};">
											{(row.diesel_pct || 0).toFixed(1)}%
										</span>
									</td>
									<td class="py-2 px-3 font-bold" style="color: #ef4444;">{row.recommendation || 'CLOSE'}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}
	{/if}

	<!-- #90 Theft/Waste Probability (Horizontal Bar) -->
	{#if anomalies?.length > 0}
		<div style="background: #383832; color: #feffd6;" class="px-4 py-2.5 font-black text-sm uppercase mt-6">THEFT / WASTE PROBABILITY</div>
		{@const sorted90 = [...anomalies].sort((a: any, b: any) => (b.score || b.waste_score || 0) - (a.score || a.waste_score || 0)).slice(0, 15)}
		<Chart option={hbarChart(
			sorted90.map((r: any) => r.site_id || r.site || ''),
			sorted90.map((r: any) => Math.round((r.score || r.waste_score || 0) * 100) / 100),
			{ title: 'Top 15 Sites by Waste/Theft Score', colors: sorted90.map((r: any) => (r.score || r.waste_score || 0) > 0.7 ? '#ef4444' : (r.score || r.waste_score || 0) > 0.4 ? '#f59e0b' : '#22c55e') }
		)} height="{Math.max(300, sorted90.length * 28)}px" guide={{ formula: "Isolation Forest anomaly score: higher = more likely fuel waste or theft. Based on variance between expected vs actual consumption.", sources: [{ data: 'Anomaly Score', file: 'anomalies API', col: 'score', method: 'Isolation Forest ML' }], reading: [{ color: 'red', text: 'Score > 0.7 = High probability of waste/theft' }, { color: 'amber', text: '0.4-0.7 = Investigate' }, { color: 'green', text: '< 0.4 = Normal' }], explain: "Machine learning flags sites where fuel usage is <b>abnormally high</b> compared to generator run hours. High scores mean fuel may be stolen or wasted." }} />
	{/if}

	<!-- #91 Delivery Schedule Table -->
	{#if deliveryQueue?.length > 0}
		<div style="background: #383832; color: #feffd6;" class="px-4 py-2.5 font-black text-sm uppercase mt-6">DELIVERY SCHEDULE</div>
		<div style="border: 2px solid #383832; background: white;">
			<div class="px-4 py-2 flex justify-between" style="background: #383832; color: #feffd6;">
				<span class="font-bold uppercase text-sm">Upcoming Fuel Deliveries</span>
				<button onclick={() => downloadExcel(deliveryQueue, 'Delivery Schedule', { statusColumns: ['urgency'] })}
					class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
					style="color: #00fc40;">
					<span class="material-symbols-outlined text-sm">download</span> EXCEL
				</button>
			</div>
			<div class="overflow-x-auto">
				<table class="w-full text-xs">
					<thead><tr style="background: #ebe8dd;">
						<th class="py-2 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">Site</th>
						<th class="py-2 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">Site_Code</th>
						<th class="py-2 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">Urgency</th>
						<th class="py-2 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">Days Left</th>
						<th class="py-2 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">Liters Needed</th>
						<th class="py-2 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">Deliver By</th>
					</tr></thead>
					<tbody>
						{#each deliveryQueue as row, i}
							<tr style="background: {i % 2 ? '#f6f4e9' : 'white'}; border-bottom: 1px solid #ebe8dd;">
								<td class="py-2 px-3 font-bold">{row.site_id || row.site || '-'}</td>
								<td class="py-2 px-3 font-mono text-xs">{row.site_code || row.region || ''}</td>
								<td class="py-2 px-3">
									<span class="px-2 py-0.5 rounded text-white text-xs font-bold" style="background: {(row.urgency || '').toLowerCase() === 'critical' ? '#ef4444' : (row.urgency || '').toLowerCase() === 'high' ? '#f59e0b' : '#3b82f6'};">
										{row.urgency || '-'}
									</span>
								</td>
								<td class="py-2 px-3">{(row.days_left ?? row.days_remaining ?? '-')}</td>
								<td class="py-2 px-3">{Math.round(row.liters_needed || row.liters || 0).toLocaleString()} L</td>
								<td class="py-2 px-3">{row.deliver_by || row.deadline || '-'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}

	<!-- #93 Weekly Budget Forecast KPI Cards -->
	{#if fuelIntel?.weekly_budget}
		<div style="background: #383832; color: #feffd6;" class="px-4 py-2.5 font-black text-sm uppercase mt-6">WEEKLY BUDGET FORECAST</div>
		{@const wb = fuelIntel.weekly_budget}
		<div class="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3">
			<div class="rounded-lg p-4 text-center" style="background: #3b82f6; color: white;">
				<div class="text-xs font-bold uppercase opacity-80">Weekly Fuel</div>
				<div class="text-2xl font-black">{Math.round(wb.weekly_liters || wb.total_liters || 0).toLocaleString()} L</div>
				<div class="text-xs opacity-80">projected consumption</div>
			</div>
			<div class="rounded-lg p-4 text-center" style="background: #8b5cf6; color: white;">
				<div class="text-xs font-bold uppercase opacity-80">Weekly Cost</div>
				<div class="text-2xl font-black">{(Math.round((wb.weekly_cost || wb.total_cost || 0) / 1e6 * 10) / 10).toLocaleString()}M MMK</div>
				<div class="text-xs opacity-80">estimated spend</div>
			</div>
			<div class="rounded-lg p-4 text-center" style="background: #06b6d4; color: white;">
				<div class="text-xs font-bold uppercase opacity-80">Daily Average</div>
				<div class="text-2xl font-black">{Math.round(wb.daily_avg || wb.daily_average || (wb.weekly_liters || 0) / 7).toLocaleString()} L</div>
				<div class="text-xs opacity-80">liters per day</div>
			</div>
		</div>
	{/if}
{/if}
