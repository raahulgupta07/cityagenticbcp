<script lang="ts">
	let activeDict = $state('thresholds');

	const dictTabs = [
		{ id: 'thresholds', label: 'THRESHOLDS', icon: 'tune' },
		{ id: 'kpis', label: 'KPI_DICTIONARY', icon: 'calculate' },
		{ id: 'modes', label: 'OP_MODES', icon: 'settings_suggest' },
		{ id: 'grades', label: 'BCP_GRADES', icon: 'grade' },
		{ id: 'alerts', label: 'ALERTS', icon: 'notifications' },
		{ id: 'reference', label: 'REFERENCE', icon: 'menu_book' },
		{ id: 'navigation', label: 'NAV_GUIDE', icon: 'map' },
	];

	const thresholds = [
		{ icon: 'check_circle', color: '#007518', label: 'GREEN / SAFE', diesel: '< 3,500', bo: '< 4 HR', exp: '< 0.9%', buffer: '> 7 DAYS' },
		{ icon: 'visibility', color: '#ff9d00', label: 'YELLOW / WATCH', diesel: '3,500 - 5,000', bo: '4 - 8 HR', exp: '0.9 - 1.5%', buffer: '5 - 7 DAYS' },
		{ icon: 'warning', color: '#f95630', label: 'AMBER / WARNING', diesel: '5,001 - 8,000', bo: '8 - 12 HR', exp: '1.5 - 3%', buffer: '3 - 5 DAYS' },
		{ icon: 'emergency', color: '#be2d06', label: 'RED / CRITICAL', diesel: '> 8,000', bo: '> 12 HR', exp: '> 3%', buffer: '< 3 DAYS' },
	];

	const kpis = [
		{ id: '001', name: 'Buffer Days', formula: 'Tank ÷ (7d_Avg_Blackout × Rated_L/Hr)', unit: 'DAYS', source: 'BLACKOUT_EXCEL', tag: 'Critical', tagColor: '#007518', explain: 'How many days of fuel remain based on blackout-driven consumption rate' },
		{ id: '002', name: 'Daily Burn', formula: 'SUM(Daily_Used) ÷ COUNT(days)', unit: 'LITERS', source: 'BLACKOUT_EXCEL', tag: 'Ops', tagColor: '#9d4867', explain: 'Average daily fuel consumption across all generators at a site' },
		{ id: '003', name: 'Diesel Cost', formula: 'Daily_Used × Date_Specific_Price', unit: 'MMK', source: 'BLACKOUT+FUEL', tag: 'Finance', tagColor: '#006f7c', explain: 'Daily cost using the most recent purchase price on or before that date' },
		{ id: '004', name: 'Diesel %', formula: '(Liters × Price) ÷ Sales × 100', unit: 'PERCENT', source: 'ALL_EXCEL', tag: 'Critical', tagColor: '#007518', explain: 'Key decision metric — if above 3%, store may not be worth keeping open' },
		{ id: '005', name: 'Efficiency', formula: 'Liters ÷ Gen_Hours', unit: 'L/HR', source: 'BLACKOUT_EXCEL', tag: 'Process', tagColor: '#006f7c', explain: 'Fuel economy of the generator. Should be flat — spikes mean waste or theft' },
		{ id: '006', name: 'Variance', formula: 'Actual - (Rated_L/Hr × Hours)', unit: 'LITERS', source: 'BLACKOUT_EXCEL', tag: 'High Risk', tagColor: '#be2d06', explain: 'Gap between expected and actual consumption — large gaps signal problems' },
		{ id: '007', name: 'Peak Hours', formula: 'Avg_Hourly_Sales ÷ Diesel_Cost/Hr', unit: 'RATIO', source: 'HOURLY_SALES', tag: 'Revenue', tagColor: '#9d4867', explain: 'Revenue earned per unit of diesel cost during each hour of operation' },
		{ id: '008', name: 'Blackout Hr', formula: 'MAX(blackout_per_date_per_site)', unit: 'HOURS', source: 'BLACKOUT_EXCEL', tag: 'Ops', tagColor: '#9d4867', explain: 'Maximum hours without city power per day — drives generator runtime' },
		{ id: '009', name: 'Tank Balance', formula: 'Spare_Tank_Balance(latest)', unit: 'LITERS', source: 'BLACKOUT_EXCEL', tag: 'Critical', tagColor: '#007518', explain: 'Current fuel level in the tank — the starting point for buffer calculation' },
		{ id: '010', name: 'Gen Run Hr', formula: 'SUM(gen_run_hr_per_site_day)', unit: 'HOURS', source: 'BLACKOUT_EXCEL', tag: 'Asset', tagColor: '#007518', explain: 'Total generator running hours — used for maintenance scheduling' },
		{ id: '011', name: 'BCP Score', formula: 'Fuel(35%)+Coverage(30%)+Power(20%)+Resil(15%)', unit: 'INDEX', source: 'CALCULATED', tag: 'Critical', tagColor: '#007518', explain: 'Weighted composite score measuring overall site resilience (A-F grades)' },
		{ id: '012', name: 'Waste Score', formula: '(Actual_LPH ÷ Rated_LPH - 1) × 100', unit: 'PERCENT', source: 'CALCULATED', tag: 'High Risk', tagColor: '#be2d06', explain: 'Percentage over-consumption vs rated specification — flags theft/leaks' },
		{ id: '013', name: 'Utilization', formula: 'Active_Days ÷ Total_Days × 100', unit: 'PERCENT', source: 'CALCULATED', tag: 'Infra', tagColor: '#006f7c', explain: 'How often the generator is actually used — low = idle asset cost' },
		{ id: '014', name: 'Weekly Budget', formula: 'Avg_Daily_Liters × 7 × Price', unit: 'MMK', source: 'CALCULATED', tag: 'Finance', tagColor: '#006f7c', explain: 'Projected weekly fuel expenditure for procurement planning' },
		{ id: '015', name: 'Net Margin', formula: 'Sales - Energy_Cost', unit: 'MMK', source: 'SALES+ENERGY', tag: 'Revenue', tagColor: '#9d4867', explain: 'Revenue minus diesel cost — the real profitability during blackouts' },
		{ id: '016', name: 'Diesel Needed', formula: 'SUM(7 × Avg_Burn - Tank)', unit: 'LITERS', source: 'CALCULATED', tag: 'Compliance', tagColor: '#be2d06', explain: 'Total liters needed across all sites below 7-day buffer threshold' },
	];

	const modes = [
		{ id: '00', name: 'FULL', bg: '#007518', text: '#feffd6', icon: 'check_circle', desc: 'All systems operational. Grid power priority. Standard cooling protocols active.' },
		{ id: '01', name: 'MONITOR', bg: '#ff9d00', text: '#383832', icon: 'visibility', desc: 'Detected grid instability. Enhanced telemetry logging. Ready emergency assets.' },
		{ id: '02', name: 'REDUCE', bg: '#f95630', text: '#feffd6', icon: 'trending_down', desc: 'Load shedding initiated. Non-critical systems powered down. Optimize for runtime.' },
		{ id: '03', name: 'GEN_ONLY', bg: '#6d4c41', text: '#feffd6', icon: 'precision_manufacturing', desc: 'Total grid failure. Diesel assets engaged. Strict fuel consumption monitoring.' },
		{ id: '04', name: 'CLOSE', bg: '#be2d06', text: '#feffd6', icon: 'dangerous', desc: 'Critical breach or depletion. Orderly shutdown. All data mirrors locked.' },
	];

	const bcpGrades = [
		{ grade: 'A', range: '80-100', label: 'RESILIENT', labelBg: '#007518', desc: 'Hardened infrastructure with multi-layer redundancy.' },
		{ grade: 'B', range: '60-79', label: 'ADEQUATE', labelBg: '#007518', desc: 'Standard operational safety. Redundancies tested and confirmed.' },
		{ grade: 'C', range: '40-59', label: 'AT RISK', labelBg: '#ff9d00', desc: 'Single points of failure identified. Manual intervention required.' },
		{ grade: 'D', range: '20-39', label: 'VULNERABLE', labelBg: '#f95630', desc: 'Significant gaps in backup protocols. High probability of latency.' },
		{ grade: 'F', range: '0-19', label: 'CRITICAL', labelBg: '#be2d06', desc: 'Non-compliant. High risk of total systemic failure.' },
	];

	const alertLevels = [
		{ severity: 'CRITICAL', bg: '#be2d06', icon: 'emergency', examples: 'Buffer < 3 days, Price surge > 20%, Blackout > 8hr, Energy cost > 60%' },
		{ severity: 'WARNING', bg: '#ff9d00', icon: 'warning', examples: 'Buffer 3-7 days, Price spike > 10%, Gen idle 3+ days, Efficiency anomaly' },
		{ severity: 'INFO', bg: '#006f7c', icon: 'info', examples: 'Missing data 2+ days, General notifications, Sync events' },
	];

	const dataSources = [
		{ file: 'Blackout Hr_ CFC.xlsx', sheets: 'CFC', data: 'CFC generators, fuel usage, tank balance, blackout hours' },
		{ file: 'Blackout Hr_ CMHL.xlsx', sheets: 'CMHL', data: 'CMHL generators, fuel usage, tank balance' },
		{ file: 'Blackout Hr_ CP.xlsx', sheets: 'CP', data: 'CP generators, fuel usage, tank balance, blackout hours' },
		{ file: 'Blackout Hr_ PG.xlsx', sheets: 'PG', data: 'PG generators, fuel usage, tank balance, blackout hours' },
		{ file: 'Daily Fuel Price.xlsx', sheets: 'CMHL,CP,CFC,PG', data: 'Supplier prices, fuel type, quantity' },
		{ file: 'CMHL_DAILY_SALES.xlsx', sheets: 'daily/hourly/STORE MASTER', data: 'Revenue, margin, hourly transactions' },
		{ file: 'Diesel Expense LY.xlsx', sheets: 'Various', data: 'Last-year baseline expense' },
	];
</script>

<!-- Dictionary Tab Bar -->
<div class="mb-6">
	<div class="flex flex-wrap" style="border: 2px solid #383832; border-bottom: 0;">
		{#each dictTabs as tab}
			<button
				onclick={() => activeDict = tab.id}
				class="px-4 py-2.5 text-[10px] font-black uppercase flex items-center gap-1.5 transition-colors"
				style="{activeDict === tab.id
					? 'background: #383832; color: #feffd6;'
					: 'background: #ebe8dd; color: #383832; border-right: 1px solid #383832;'}"
			>
				<span class="material-symbols-outlined text-sm">{tab.icon}</span>
				{tab.label}
			</button>
		{/each}
	</div>

	<!-- Tab Content -->
	<div class="p-6" style="border: 2px solid #383832; min-height: 300px;">

		<!-- THRESHOLDS -->
		{#if activeDict === 'thresholds'}
			<div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
				<div class="lg:col-span-9" style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
					<div class="px-4 py-2 font-black uppercase text-sm" style="background: #383832; color: #feffd6;">ACTIVE_THRESHOLD_METRICS</div>
					<table class="w-full text-left text-sm" style="border-collapse: collapse;">
						<thead>
							<tr style="background: #ebe8dd; border-bottom: 2px solid #383832;">
								<th class="px-4 py-3 font-black uppercase" style="border-right: 2px solid #383832;">Status</th>
								<th class="px-4 py-3 font-black uppercase" style="border-right: 2px solid #383832;">Risk Level</th>
								<th class="px-4 py-3 font-black uppercase" style="border-right: 2px solid #383832;">Diesel (MMK/L)</th>
								<th class="px-4 py-3 font-black uppercase" style="border-right: 2px solid #383832;">Blackout HR</th>
								<th class="px-4 py-3 font-black uppercase" style="border-right: 2px solid #383832;">Expense %</th>
								<th class="px-4 py-3 font-black uppercase">Buffer</th>
							</tr>
						</thead>
						<tbody>
							{#each thresholds as t, i}
								<tr style="border-bottom: 2px solid #383832; background: {i % 2 ? '#fcf9ef' : 'white'};">
									<td class="px-4 py-4 text-center" style="border-right: 2px solid #383832;">
										<div class="w-8 h-8 flex items-center justify-center text-white mx-auto" style="background: {t.color};">
											<span class="material-symbols-outlined text-base" style="font-variation-settings: 'FILL' 1;">{t.icon}</span>
										</div>
									</td>
									<td class="px-4 py-4 font-bold" style="border-right: 2px solid #383832; color: {t.color};">{t.label}</td>
									<td class="px-4 py-4 font-mono" style="border-right: 2px solid #383832;">{t.diesel}</td>
									<td class="px-4 py-4 font-mono" style="border-right: 2px solid #383832;">{t.bo}</td>
									<td class="px-4 py-4 font-mono" style="border-right: 2px solid #383832;">{t.exp}</td>
									<td class="px-4 py-4 font-mono font-bold" style="color: {t.color};">{t.buffer}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				<div class="lg:col-span-3 space-y-4">
					<div class="p-4" style="background: #00fc40; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
						<div class="font-black text-sm mb-1" style="border-bottom: 1px solid #383832; padding-bottom: 4px;">CURR_STATUS</div>
						<div class="text-3xl font-black">OK</div>
						<div class="text-[10px] font-bold uppercase mt-1">All thresholds within limits</div>
					</div>
					<div class="p-4 text-xs space-y-2" style="background: #ebe8dd; border: 2px solid #383832;">
						<div class="font-black uppercase text-[10px] mb-2" style="border-bottom: 1px solid #383832; padding-bottom: 4px;">PROTOCOL_LOG</div>
						<p>Diesel thresholds calibrated for Myanmar market (MMK).</p>
						<p>Buffer = blackout-based (not refill-based).</p>
						<p>Icons only — no background colors in exports.</p>
					</div>
				</div>
			</div>

		<!-- KPI DICTIONARY -->
		{:else if activeDict === 'kpis'}
			<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
				{#each kpis as k}
					<div class="flex gap-4 p-4" style="background: white; border: 2px solid #383832; border-bottom-width: 4px; border-right-width: 4px;">
						<div class="shrink-0 w-12 h-12 flex items-center justify-center font-black text-lg" style="background: {k.tagColor}; color: #feffd6;">
							{k.id}
						</div>
						<div class="flex-1 min-w-0">
							<div class="flex items-center gap-2 mb-1">
								<span class="font-black uppercase text-sm" style="color: #383832;">{k.name}</span>
								<span class="px-1.5 py-0.5 text-[8px] font-bold uppercase" style="background: {k.tagColor}; color: white;">{k.tag}</span>
							</div>
							<div class="px-2 py-1 font-mono text-[11px] mb-2" style="background: #383832; color: #00ff41;">{k.formula}</div>
							<p class="text-[11px] mb-2" style="color: #65655e;">{k.explain}</p>
							<div class="flex gap-4 text-[10px] font-bold uppercase" style="color: #65655e; border-top: 1px solid #ebe8dd; padding-top: 4px;">
								<span>UNIT: <span style="color: #383832;">{k.unit}</span></span>
								<span>SRC: <span style="color: #006f7c;">{k.source}</span></span>
							</div>
						</div>
					</div>
				{/each}
			</div>

		<!-- OPERATING MODES -->
		{:else if activeDict === 'modes'}
			<div class="grid grid-cols-1 md:grid-cols-5 gap-0" style="border: 3px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
				{#each modes as m, i}
					<div class="p-5 flex flex-col justify-between min-h-[200px]" style="background: {m.bg}; color: {m.text}; {i < 4 ? 'border-right: 3px solid #383832;' : ''}">
						<div>
							<div class="flex justify-between items-start">
								<span class="text-[10px] font-black uppercase px-1" style="border: 1px solid {m.text};">MODE_{m.id}</span>
								<span class="material-symbols-outlined">{m.icon}</span>
							</div>
							<h3 class="text-3xl font-black mt-4 leading-none uppercase">{m.name}</h3>
						</div>
						<p class="text-xs font-medium leading-tight mt-4">{m.desc}</p>
					</div>
				{/each}
			</div>

		<!-- BCP GRADES -->
		{:else if activeDict === 'grades'}
			<div class="grid grid-cols-1 md:grid-cols-5 gap-4">
				{#each bcpGrades as g}
					<div class="text-center" style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
						<div class="py-4" style="background: {g.labelBg};">
							<span class="text-5xl font-black" style="color: #feffd6;">{g.grade}</span>
						</div>
						<div class="p-4">
							<div class="font-mono text-sm font-bold mb-1" style="color: #383832;">{g.range}</div>
							<div class="px-2 py-0.5 text-[10px] font-black uppercase inline-block mb-2" style="background: {g.labelBg}; color: #feffd6;">{g.label}</div>
							<p class="text-[11px]" style="color: #65655e;">{g.desc}</p>
						</div>
					</div>
				{/each}
			</div>

		<!-- ALERTS -->
		{:else if activeDict === 'alerts'}
			<div class="grid grid-cols-1 md:grid-cols-3 gap-0" style="border: 3px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
				{#each alertLevels as a, i}
					<div class="p-6 flex flex-col gap-3" style="background: {a.bg}; color: white; {i < 2 ? 'border-right: 3px solid #383832;' : ''}">
						<div class="flex justify-between items-start">
							<span class="text-[10px] font-black uppercase px-1" style="border: 1px solid white;">LEVEL_{String(i).padStart(2, '0')}</span>
							<span class="material-symbols-outlined">{a.icon}</span>
						</div>
						<h3 class="text-3xl font-black uppercase leading-none">{a.severity}</h3>
						<p class="text-xs font-medium leading-relaxed mt-auto">{a.examples}</p>
					</div>
				{/each}
			</div>

		<!-- REFERENCE -->
		{:else if activeDict === 'reference'}
			<div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
				<!-- Icon Reference -->
				<div style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
					<div class="px-4 py-2 font-black uppercase text-sm" style="background: #383832; color: #feffd6;">ICON_REFERENCE</div>
					<div class="p-4 grid grid-cols-2 gap-2 text-xs font-bold uppercase">
						{#each [
							['🟢','Safe / Nominal'], ['🟡','Watch / Caution'], ['🟠','Warning / Elevated'], ['🔴','Critical / Danger'],
							['⚪','No Data / Null'], ['⚙️','Generator / Fleet'], ['⛽','Fuel / Diesel'], ['📊','Analytics'],
							['🔧','Tool Call (AI)'], ['🧠','AI Insight'], ['🗺️','Sector Map'], ['📅','Calendar / Date'],
						] as [icon, label]}
							<div class="flex items-center gap-2 p-2" style="background: white; border: 1px solid #383832;">
								<span class="text-lg">{icon}</span>
								<span style="color: #383832;">{label}</span>
							</div>
						{/each}
					</div>
				</div>

				<!-- Data Sources -->
				<div style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
					<div class="px-4 py-2 font-black uppercase text-sm" style="background: #383832; color: #feffd6;">DATA_SOURCES</div>
					<table class="w-full text-xs" style="border-collapse: collapse;">
						<thead>
							<tr style="background: #ebe8dd; border-bottom: 2px solid #383832;">
								<th class="px-3 py-2 text-left font-black uppercase" style="border-right: 2px solid #383832;">File</th>
								<th class="px-3 py-2 text-left font-black uppercase" style="border-right: 2px solid #383832;">Sheets</th>
								<th class="px-3 py-2 text-left font-black uppercase">Data</th>
							</tr>
						</thead>
						<tbody>
							{#each dataSources as d, i}
								<tr style="border-bottom: 1px solid #ebe8dd; background: {i % 2 ? '#fcf9ef' : 'white'};">
									<td class="px-3 py-2 font-mono font-bold" style="border-right: 2px solid #383832; color: #383832;">{d.file}</td>
									<td class="px-3 py-2 font-bold" style="border-right: 2px solid #383832; color: #006f7c;">{d.sheets}</td>
									<td class="px-3 py-2" style="color: #65655e;">{d.data}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		<!-- NAVIGATION GUIDE -->
		{:else if activeDict === 'navigation'}
			<div style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
				<div class="px-4 py-2 font-black uppercase text-sm" style="background: #383832; color: #feffd6;">DASHBOARD_NAVIGATION_GUIDE</div>
				<table class="w-full text-xs" style="border-collapse: collapse;">
					<thead>
						<tr style="background: #ebe8dd; border-bottom: 2px solid #383832;">
							<th class="px-4 py-2 text-left font-black uppercase" style="border-right: 2px solid #383832;">TAB</th>
							<th class="px-4 py-2 text-left font-black uppercase" style="border-right: 2px solid #383832;">LEVEL</th>
							<th class="px-4 py-2 text-left font-black uppercase" style="border-right: 2px solid #383832;">WHAT_IT_SHOWS</th>
							<th class="px-4 py-2 text-left font-black uppercase">KEY_DECISION</th>
						</tr>
					</thead>
					<tbody>
						{#each [
							{ tab: 'TRENDS', level: 'Group/Sector', what: '19 charts — fuel burn, efficiency, buffer, rolling averages, daily vs 3-day', decision: 'Are things getting better or worse? Where is the trend heading?' },
							{ tab: 'SECTOR', level: 'Group', what: 'Heatmap, rankings, Regular vs LNG comparison', decision: 'Which sector needs attention? Which sites are worst?' },
							{ tab: 'OPS_FLEET', level: 'Site/Generator', what: 'Operating modes, delivery queue, maintenance, transfers, anomalies', decision: 'Which sites to close? Where to send fuel? Which generators need service?' },
							{ tab: 'RISK', level: 'Site', what: 'BCP scores (A-F), recommendations, alerts, stockout forecast', decision: 'Which sites will run out of fuel? What actions are urgent?' },
							{ tab: 'FUEL_INTEL', level: 'Supplier/Sector', what: 'Buy signals, weekly budget, price forecast, break-even, site mapping', decision: 'Should we buy fuel now? Which stores should close?' },
							{ tab: 'FORECAST', level: 'Site/Group', what: 'ML predictions, what-if scenarios, stockout projections', decision: 'What happens if price goes up 20%? When will sites run out?' },
							{ tab: 'AI', level: 'All', what: 'Gemini-powered morning briefing, KPI analysis, site insights', decision: 'What did AI find that humans might miss?' },
							{ tab: 'SITE_DIVE', level: 'Site', what: '18 charts per site — buffer, efficiency, gen hours, fuel, cost, anomaly', decision: 'Deep dive into one specific site\'s performance' },
							{ tab: 'DICTIONARY', level: 'Reference', what: 'Thresholds, KPI formulas, operating modes, grades, alerts', decision: 'What does each metric mean? How is it calculated?' },
						] as row, i}
							<tr style="border-bottom: 1px solid #ebe8dd; background: {i % 2 ? '#f6f4e9' : 'white'};">
								<td class="px-4 py-2 font-black" style="border-right: 2px solid #383832; color: #007518;">{row.tab}</td>
								<td class="px-4 py-2 font-bold" style="border-right: 2px solid #383832; color: #006f7c;">{row.level}</td>
								<td class="px-4 py-2" style="border-right: 2px solid #383832; color: #383832;">{row.what}</td>
								<td class="px-4 py-2" style="color: #65655e;">{row.decision}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>
</div>
