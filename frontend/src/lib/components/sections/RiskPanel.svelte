<script lang="ts">
	import { api, downloadExcel } from '$lib/api';
	import { onMount } from 'svelte';

	let scores: any[] = $state([]);
	let distribution: any = $state({});
	let recommendations: any[] = $state([]);
	let alerts: any[] = $state([]);
	let alertCounts: any = $state({});
	let forecast: any[] = $state([]);
	let critical: any[] = $state([]);
	let loading = $state(true);
	let error = $state('');

	const gradeColors: Record<string, string> = {
		A: '#007518',
		B: '#007518',
		C: '#ff9d00',
		D: '#f95630',
		F: '#be2d06',
	};

	const severityColors: Record<string, string> = {
		critical: '#be2d06',
		warning: '#ff9d00',
		info: '#006f7c',
	};

	const severityOrder = ['critical', 'warning', 'info'];

	function sortedScores(list: any[]): any[] {
		return [...list].sort((a, b) => (a.score ?? 0) - (b.score ?? 0));
	}

	function sortedForecast(list: any[]): any[] {
		return [...list].sort((a, b) => (a.days_left ?? 0) - (b.days_left ?? 0));
	}

	function groupedAlerts(list: any[]): any[] {
		const groups: any[] = [];
		for (const sev of severityOrder) {
			const items = list.filter((a) => (a.severity || '').toLowerCase() === sev);
			if (items.length) groups.push(...items);
		}
		const rest = list.filter((a) => !severityOrder.includes((a.severity || '').toLowerCase()));
		groups.push(...rest);
		return groups;
	}

	function trendArrow(trend: string | undefined): string {
		if (!trend) return '\u2192';
		const t = trend.toLowerCase();
		if (t === 'up' || t === 'increasing') return '\u2191';
		if (t === 'down' || t === 'decreasing') return '\u2193';
		return '\u2192';
	}

	let search = $state('');
	const matchSearch = (r: any) => Object.values(r).some(v => String(v).toLowerCase().includes(search.toLowerCase()));
	const filteredScores = $derived(search ? scores.filter(matchSearch) : scores);
	const filteredAlerts = $derived(search ? alerts.filter(matchSearch) : alerts);
	const filteredForecast = $derived(search ? forecast.filter(matchSearch) : forecast);

	async function load() {
		loading = true;
		error = '';
		try {
			const [s, r, a, f] = await Promise.all([
				api.get('/bcp-scores'),
				api.get('/recommendations'),
				api.get('/alerts/active'),
				api.get('/stockout-forecast'),
			]);
			scores = s.scores || [];
			distribution = s.distribution || {};
			recommendations = r.recommendations || [];
			alerts = a.alerts || [];
			alertCounts = a.counts || {};
			forecast = f.forecast || [];
			critical = f.critical || [];
		} catch (e) {
			console.error(e);
			error = 'Failed to load risk panel data. Check your connection and try again.';
		} finally {
			loading = false;
		}
	}

	onMount(load);
</script>

<div class="risk-panel">
	{#if loading}
		<div class="loading">LOADING_DATA...</div>
	{:else if error}
		<div class="text-center py-12" style="background: #f6f4e9; border: 2px solid #383832;">
			<span class="material-symbols-outlined text-3xl" style="color: #be2d06;">error</span>
			<p class="font-bold mt-2 uppercase text-xs" style="color: #be2d06;">{error}</p>
			<button onclick={load} class="mt-3 px-4 py-1.5 text-[10px] font-black uppercase"
				style="background: #383832; color: #feffd6; border: 2px solid #383832;">
				<span class="material-symbols-outlined text-xs align-middle">refresh</span> RETRY
			</button>
		</div>
	{:else if scores.length === 0 && alerts.length === 0 && forecast.length === 0}
		<div class="text-center py-12" style="background: #f6f4e9; border: 2px solid #383832;">
			<span class="material-symbols-outlined text-3xl" style="color: #65655e;">inbox</span>
			<p class="font-bold mt-2 uppercase text-xs" style="color: #383832;">NO DATA AVAILABLE</p>
			<p class="text-[10px] mt-1" style="color: #65655e;">Upload data or adjust your filters.</p>
		</div>
	{:else}
		<div class="px-3 py-2 flex items-center gap-2" style="background: #ebe8dd; border-bottom: 1px solid #383832; border: 2px solid #383832; margin-bottom: 1rem;">
			<span class="material-symbols-outlined text-sm" style="color: #65655e;">search</span>
			<input type="text" bind:value={search} placeholder="QUICK_SEARCH..."
				class="flex-1 px-2 py-1 text-xs font-mono uppercase"
				style="background: white; border: 1px solid #383832; color: #383832;" />
		</div>

		<!-- ═══════ SECTION 1: BCP RISK SCORES ═══════ -->
		<section class="panel-section">
			<div class="section-header">
			<span>BCP_RISK_SCORES</span>
			<button onclick={() => downloadExcel(scores, 'BCP Scores', { statusColumns: ['grade'] })}
				class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
				style="color: #00fc40;">
				<span class="material-symbols-outlined text-sm">download</span> EXCEL
			</button>
		</div>
			<div class="section-body">
				<div class="grade-distribution">
					{#each ['A', 'B', 'C', 'D', 'F'] as grade}
						<div class="grade-box" style="border-color: {gradeColors[grade]}">
							<span class="grade-letter" style="color: {gradeColors[grade]}">{grade}</span>
							<span class="grade-count">{distribution[grade] ?? 0}</span>
						</div>
					{/each}
				</div>

				<div class="table-wrap">
					<table>
						<thead>
							<tr>
								<th>SITE_ID</th>
								<th>SITE_CODE</th>
								<th>SEGMENT</th>
								<th>SECTOR</th>
								<th>SCORE</th>
								<th>GRADE</th>
								<th>FUEL_SCORE</th>
								<th>COVERAGE</th>
								<th>POWER</th>
								<th>RESILIENCE</th>
							</tr>
						</thead>
						<tbody>
							{#each sortedScores(filteredScores) as row, i}
								<tr class={i % 2 === 0 ? 'row-even' : 'row-odd'}>
									<td class="mono">{row.site_id ?? ''}</td>
									<td class="mono">{row.site_code || row.region || ''}</td>
									<td>{row.segment_name || ''}</td>
									<td>{row.sector ?? ''}</td>
									<td class="num">{row.score ?? ''}</td>
									<td>
										<span
											class="grade-badge"
											style="background: {gradeColors[row.grade] ?? '#383832'}; color: #feffd6;"
										>
											{row.grade ?? ''}
										</span>
									</td>
									<td class="num">{row.fuel_score ?? ''}</td>
									<td class="num">{row.coverage ?? ''}</td>
									<td class="num">{row.power ?? ''}</td>
									<td class="num">{row.resilience ?? ''}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		</section>

		<!-- ═══════ SECTION 2: RECOMMENDATIONS ═══════ -->
		<section class="panel-section">
			<div class="section-header">RECOMMENDATIONS</div>
			<div class="section-body">
				<div class="rec-cards">
					{#each recommendations as rec}
						{@const severity = (rec.severity || rec.type || 'info').toLowerCase()}
						{@const borderColor = severityColors[severity] ?? severityColors.info}
						<div class="rec-card" style="border-left: 4px solid {borderColor};">
							<div class="rec-title" style="color: {borderColor};">{rec.title ?? 'RECOMMENDATION'}</div>
							<div class="rec-message">{rec.message ?? ''}</div>
							{#if rec.affected_sites != null}
								<div class="rec-sites">AFFECTED_SITES: {rec.affected_sites}</div>
							{/if}
						</div>
					{/each}
					{#if recommendations.length === 0}
						<div class="empty">NO_RECOMMENDATIONS</div>
					{/if}
				</div>
			</div>
		</section>

		<!-- ═══════ SECTION 3: ACTIVE ALERTS ═══════ -->
		<section class="panel-section">
			<div class="section-header">
			<span>ACTIVE_ALERTS</span>
			<button onclick={() => downloadExcel(alerts, 'Active Alerts', { statusColumns: ['severity'] })}
				class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
				style="color: #00fc40;">
				<span class="material-symbols-outlined text-sm">download</span> EXCEL
			</button>
		</div>
			<div class="section-body">
				<div class="alert-counts">
					<div class="alert-count-badge" style="background: {severityColors.critical}; color: #feffd6;">
						CRITICAL: {alertCounts.critical ?? 0}
					</div>
					<div class="alert-count-badge" style="background: {severityColors.warning}; color: #383832;">
						WARNING: {alertCounts.warning ?? 0}
					</div>
					<div class="alert-count-badge" style="background: {severityColors.info}; color: #feffd6;">
						INFO: {alertCounts.info ?? 0}
					</div>
				</div>

				<div class="table-wrap">
					<table>
						<thead>
							<tr>
								<th>SEVERITY</th>
								<th>ALERT_TYPE</th>
								<th>SITE_ID</th>
								<th>SITE_CODE</th>
								<th>SECTOR</th>
								<th>MESSAGE</th>
								<th>CREATED_AT</th>
							</tr>
						</thead>
						<tbody>
							{#each groupedAlerts(filteredAlerts) as row, i}
								{@const sev = (row.severity || '').toLowerCase()}
								<tr class={i % 2 === 0 ? 'row-even' : 'row-odd'}>
									<td>
										<span
											class="severity-badge"
											style="background: {severityColors[sev] ?? '#383832'}; color: {sev === 'warning' ? '#383832' : '#feffd6'};"
										>
											{(row.severity || '').toUpperCase()}
										</span>
									</td>
									<td class="mono">{row.alert_type ?? ''}</td>
									<td class="mono">{row.site_id ?? ''}</td>
									<td class="mono">{row.site_code || row.region || ''}</td>
									<td>{row.sector ?? ''}</td>
									<td>{row.message ?? ''}</td>
									<td class="mono">{row.created_at ?? ''}</td>
								</tr>
							{/each}
							{#if alerts.length === 0}
								<tr><td colspan="7" class="empty">NO_ACTIVE_ALERTS</td></tr>
							{/if}
						</tbody>
					</table>
				</div>
			</div>
		</section>

		<!-- ═══════ SECTION 4: STOCKOUT FORECAST ═══════ -->
		<section class="panel-section">
			<div class="section-header">
				<span>STOCKOUT_FORECAST &mdash; 7_DAY
				{#if critical.length > 0}
					<span class="critical-tag">CRITICAL: {critical.length}</span>
				{/if}
				</span>
				<button onclick={() => downloadExcel(forecast, 'Stockout Forecast')}
					class="text-[10px] font-bold uppercase flex items-center gap-1 opacity-70 hover:opacity-100"
					style="color: #00fc40;">
					<span class="material-symbols-outlined text-sm">download</span> EXCEL
				</button>
			</div>
			<div class="section-body">
				<div class="table-wrap">
					<table>
						<thead>
							<tr>
								<th>SITE_ID</th>
								<th>SITE_CODE</th>
								<th>SECTOR</th>
								<th>TANK_L</th>
								<th>DAILY_BURN</th>
								<th>DAYS_LEFT</th>
								<th>STOCKOUT_DATE</th>
								<th>TREND</th>
								<th>CONFIDENCE</th>
							</tr>
						</thead>
						<tbody>
							{#each sortedForecast(filteredForecast) as row, i}
								{@const danger = (row.days_left ?? 999) < 3}
								<tr class={danger ? 'row-danger' : i % 2 === 0 ? 'row-even' : 'row-odd'}>
									<td class="mono">{row.site_id ?? ''}</td>
									<td class="mono">{row.site_code || row.region || ''}</td>
									<td>{row.sector ?? ''}</td>
									<td class="num">{row.tank_l ?? ''}</td>
									<td class="num">{row.daily_burn ?? ''}</td>
									<td class="num" style={danger ? 'font-weight:900; color:#be2d06;' : ''}>{row.days_left ?? ''}</td>
									<td class="mono">{row.stockout_date ?? ''}</td>
									<td class="trend">{trendArrow(row.trend)}</td>
									<td class="num">{row.confidence ?? ''}</td>
								</tr>
							{/each}
							{#if forecast.length === 0}
								<tr><td colspan="9" class="empty">NO_FORECAST_DATA</td></tr>
							{/if}
						</tbody>
					</table>
				</div>
			</div>
		</section>
	{/if}
</div>

<style>
	.risk-panel {
		font-family: 'IBM Plex Mono', 'Courier New', monospace;
		background: #feffd6;
		color: #383832;
		padding: 1rem;
	}

	.loading {
		text-align: center;
		padding: 3rem;
		font-weight: 900;
		text-transform: uppercase;
		letter-spacing: 0.15em;
	}

	/* ── Section chrome ── */
	.panel-section {
		border: 2px solid #383832;
		margin-bottom: 1.5rem;
	}

	.section-header {
		background: #383832;
		color: #feffd6;
		padding: 0.5rem 0.75rem;
		font-weight: 900;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		font-size: 0.85rem;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
	}

	.section-body {
		padding: 0.75rem;
	}

	/* ── Grade distribution boxes ── */
	.grade-distribution {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 0.75rem;
		flex-wrap: wrap;
	}

	.grade-box {
		border: 2px solid;
		padding: 0.5rem 1rem;
		text-align: center;
		min-width: 60px;
	}

	.grade-letter {
		display: block;
		font-weight: 900;
		font-size: 1.25rem;
		text-transform: uppercase;
	}

	.grade-count {
		display: block;
		font-weight: 900;
		font-size: 1.1rem;
	}

	.grade-badge {
		display: inline-block;
		padding: 0.1rem 0.5rem;
		font-weight: 900;
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	/* ── Tables ── */
	.table-wrap {
		overflow-x: auto;
	}

	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.8rem;
		text-transform: uppercase;
	}

	thead tr {
		background: #ebe8dd;
	}

	th {
		padding: 0.4rem 0.5rem;
		font-weight: 900;
		text-align: left;
		border-bottom: 2px solid #383832;
		white-space: nowrap;
		letter-spacing: 0.05em;
	}

	td {
		padding: 0.35rem 0.5rem;
		border-bottom: 1px solid #ddd;
	}

	.row-even {
		background: #ffffff;
	}

	.row-odd {
		background: #f6f4e9;
	}

	.row-danger {
		background: #fde2db;
	}

	.mono {
		font-family: 'IBM Plex Mono', 'Courier New', monospace;
		font-size: 0.78rem;
	}

	.num {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}

	.trend {
		text-align: center;
		font-size: 1rem;
		font-weight: 900;
	}

	.empty {
		text-align: center;
		padding: 1rem;
		font-weight: 900;
		opacity: 0.5;
		text-transform: uppercase;
	}

	/* ── Severity badges ── */
	.severity-badge {
		display: inline-block;
		padding: 0.1rem 0.45rem;
		font-weight: 900;
		font-size: 0.7rem;
		letter-spacing: 0.05em;
		white-space: nowrap;
	}

	/* ── Alert count badges ── */
	.alert-counts {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 0.75rem;
		flex-wrap: wrap;
	}

	.alert-count-badge {
		padding: 0.35rem 0.75rem;
		font-weight: 900;
		font-size: 0.8rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	/* ── Critical tag in header ── */
	.critical-tag {
		background: #be2d06;
		color: #feffd6;
		padding: 0.15rem 0.5rem;
		font-size: 0.75rem;
		font-weight: 900;
	}

	/* ── Recommendation cards ── */
	.rec-cards {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.rec-card {
		background: #ffffff;
		border: 2px solid #383832;
		padding: 0.6rem 0.75rem;
	}

	.rec-title {
		font-weight: 900;
		text-transform: uppercase;
		font-size: 0.82rem;
		letter-spacing: 0.05em;
		margin-bottom: 0.25rem;
	}

	.rec-message {
		font-size: 0.8rem;
		line-height: 1.4;
	}

	.rec-sites {
		margin-top: 0.3rem;
		font-weight: 900;
		font-size: 0.75rem;
		text-transform: uppercase;
		opacity: 0.7;
	}
</style>
