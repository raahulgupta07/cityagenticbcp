<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';

	let activeTab = $state('daily');
	let loading = $state(true);
	let message = $state('');
	let messageType = $state<'success'|'error'>('success');
	let lastSync: Record<string, any> = $state({});
	let uploadSection = $state('daily');
	let dragover = $state(false);

	interface QueueItem { file: File; filename: string; size: number; status: 'VALIDATING'|'VALIDATED'|'INVALID'|'WRONG_TAB'|'UPLOADING'|'IMPORTED'|'REJECTED'; type?: string; sheets?: string[]; rows?: number; error?: string; tab?: string; validation?: any[] }
	let queue: QueueItem[] = $state([]);
	let submitting = $state(false);
	let uploadProgress = $state({ current: 0, total: 0, filename: '', startTime: 0 });
	let elapsed = $state(0);
	let elapsedTimer: any = null;

	// Other tabs
	let summaryData: any = $state(null);
	let summaryMetric = $state('total_daily_used');
	let summarySector = $state('');
	let rawTable = $state('sites');
	let rawData: any = $state({ rows: [], count: 0 });
	let rawSearch = $state('');
	let history: any = $state({ uploads: [], totals: {} });

	const METRICS = [
		{ key: 'total_gen_run_hr', label: 'GEN_RUN_HOURS' }, { key: 'total_daily_used', label: 'DAILY_DIESEL_USED' },
		{ key: 'spare_tank_balance', label: 'TANK_BALANCE' }, { key: 'blackout_hr', label: 'BLACKOUT_HOURS' },
		{ key: 'days_of_buffer', label: 'BUFFER_DAYS' }, { key: 'num_generators_active', label: 'ACTIVE_GENERATORS' },
	];
	const RAW_TABLES = [
		{ key: 'sites', label: 'SITES' }, { key: 'generators', label: 'GENERATORS' },
		{ key: 'daily_ops', label: 'DAILY_OPS' }, { key: 'site_summary', label: 'SUMMARY' },
		{ key: 'fuel_prices', label: 'FUEL' }, { key: 'daily_sales', label: 'SALES' },
		{ key: 'hourly_sales', label: 'HOURLY' }, { key: 'store_master', label: 'STORES' },
		{ key: 'alerts', label: 'ALERTS' }, { key: 'uploads', label: 'UPLOADS' },
	];
	const SYNC_CARDS = [
		{ key: 'blackout_cmhl', label: 'CMHL', icon: 'storefront' }, { key: 'blackout_cp', label: 'CP', icon: 'apartment' },
		{ key: 'blackout_cfc', label: 'CFC', icon: 'bakery_dining' }, { key: 'blackout_pg', label: 'PG', icon: 'local_shipping' },
		{ key: 'fuel_price', label: 'FUEL', icon: 'local_gas_station' }, { key: 'combo_sales', label: 'SALES', icon: 'point_of_sale' },
		{ key: 'diesel_expense_ly', label: 'LY_EXP', icon: 'history' },
	];
	const tabs = [
		{ id: 'daily', label: 'DAILY_DATA' }, { id: 'reference', label: 'REFERENCE_DATA' },
		{ id: 'validation', label: 'DATA_QUALITY' },
		{ id: 'summary', label: 'STORE_SUMMARY' }, { id: 'raw', label: 'RAW_DATA' },
		{ id: 'model', label: 'DATA_MODEL' }, { id: 'cleaning', label: 'DATA_CLEANING' },
		{ id: 'history', label: 'HISTORY' }, { id: 'danger', label: 'DANGER_ZONE' },
	];

	let validationData: any = $state(null);
	let validationLoading = $state(false);

	async function loadValidation() {
		validationLoading = true;
		try {
			validationData = await api.get('/upload/validation');
		} catch { validationData = null; }
		validationLoading = false;
	}

	// Data model definitions
	const dataModel = [
		{ name: 'sectors', pk: 'sector_id', rows: '4', desc: 'Master sectors: CFC, CMHL, CP, PG', cols: ['sector_id [PK]', 'sector_name', 'region'], joins: [], color: '#007518' },
		{ name: 'sites', pk: 'site_id', rows: '60', desc: 'Physical locations — one per store/warehouse', cols: ['site_id [PK]', 'site_name', 'sector_id [FK→sectors]', 'site_type', 'cost_center_code', 'business_sector', 'company'], joins: ['sectors.sector_id'], color: '#007518' },
		{ name: 'generators', pk: 'generator_id', rows: '89', desc: 'Diesel generators — multiple per site', cols: ['generator_id [PK]', 'site_id [FK→sites]', 'model_name', 'power_kva', 'consumption_per_hour', 'fuel_type', 'supplier'], joins: ['sites.site_id'], color: '#006f7c' },
		{ name: 'daily_operations', pk: 'generator_id+date', rows: '740', desc: 'Per-generator per-day metrics from blackout Excel', cols: ['generator_id [FK→generators]', 'site_id [FK→sites]', 'date', 'gen_run_hr', 'daily_used_liters', 'spare_tank_balance', 'blackout_hr'], joins: ['generators.generator_id', 'sites.site_id'], color: '#006f7c' },
		{ name: 'daily_site_summary', pk: 'site_id+date', rows: '523', desc: 'Aggregated per-site per-day (materialized view)', cols: ['site_id [FK→sites]', 'date', 'total_gen_run_hr', 'total_daily_used', 'spare_tank_balance', 'blackout_hr', 'days_of_buffer', 'num_generators_active'], joins: ['sites.site_id'], color: '#9d4867' },
		{ name: 'fuel_purchases', pk: 'id', rows: '53', desc: 'Diesel purchase prices from suppliers', cols: ['sector_id [FK→sectors]', 'date', 'supplier', 'fuel_type', 'quantity_liters', 'price_per_liter'], joins: ['sectors.sector_id'], color: '#ff9d00' },
		{ name: 'daily_sales', pk: 'site_name+date+brand', rows: '126K', desc: 'Daily sales revenue per store per brand', cols: ['sales_site_name', 'site_id', 'sector_id', 'date', 'brand', 'sales_amt', 'margin'], joins: ['sites.site_id (via site_sales_map)'], color: '#9d4867' },
		{ name: 'hourly_sales', pk: 'site_name+date+hour+brand', rows: '570K', desc: 'Hourly sales + transactions for peak hour analysis', cols: ['sales_site_name', 'site_id', 'date', 'hour', 'brand', 'sales_amt', 'trans_cnt'], joins: ['sites.site_id (via site_sales_map)'], color: '#9d4867' },
		{ name: 'store_master', pk: 'gold_code', rows: '0', desc: 'SAP store reference data (GOLD_CODE, segment, location)', cols: ['gold_code [PK]', 'store_name', 'cost_center_code', 'segment_name', 'sector_id', 'channel', 'address_state'], joins: ['sectors.sector_id'], color: '#ff9d00' },
		{ name: 'site_sales_map', pk: 'sales_site_name', rows: '0', desc: 'Bridge: maps sales site names → BCP site_ids', cols: ['sales_site_name [PK]', 'site_id [FK→sites]', 'sector_id [FK→sectors]', 'gold_code', 'match_method'], joins: ['sites.site_id', 'sectors.sector_id'], color: '#ff9d00' },
		{ name: 'diesel_expense_ly', pk: 'cost_center_code', rows: '361', desc: 'Last-year baseline diesel expense per store', cols: ['cost_center_code [PK]', 'sector_id', 'cost_center_name', 'yearly_expense_mmk_mil', 'daily_avg_expense_mmk', 'pct_on_sales'], joins: [], color: '#be2d06' },
		{ name: 'alerts', pk: 'id', rows: '36', desc: 'Auto-generated alerts (10 conditions)', cols: ['alert_type', 'severity', 'site_id', 'sector_id', 'message', 'metric_value', 'threshold', 'is_acknowledged'], joins: [], color: '#be2d06' },
		{ name: 'upload_history', pk: 'id', rows: '28', desc: 'File upload audit trail', cols: ['filename', 'file_type', 'sector_id', 'rows_parsed', 'rows_accepted', 'rows_rejected', 'uploaded_at'], joins: [], color: '#65655e' },
		{ name: 'users', pk: 'id', rows: '1', desc: 'Auth: super_admin / admin / user roles', cols: ['username [PK]', 'password_hash', 'display_name', 'email', 'role', 'sectors', 'is_active'], joins: [], color: '#65655e' },
		{ name: 'generator_name_map', pk: 'raw_name', rows: '50', desc: 'Typo corrections: raw Excel name → canonical', cols: ['raw_name [PK]', 'canonical_name', 'auto_mapped'], joins: [], color: '#65655e' },
	];

	const relationships = [
		{ from: 'sectors', to: 'sites', label: '1:N', key: 'sector_id' },
		{ from: 'sites', to: 'generators', label: '1:N', key: 'site_id' },
		{ from: 'generators', to: 'daily_operations', label: '1:N', key: 'generator_id' },
		{ from: 'sites', to: 'daily_operations', label: '1:N', key: 'site_id' },
		{ from: 'sites', to: 'daily_site_summary', label: '1:N', key: 'site_id' },
		{ from: 'sectors', to: 'fuel_purchases', label: '1:N', key: 'sector_id' },
		{ from: 'sites', to: 'site_sales_map', label: '1:1', key: 'site_id' },
		{ from: 'site_sales_map', to: 'daily_sales', label: '1:N', key: 'sales_site_name' },
		{ from: 'site_sales_map', to: 'hourly_sales', label: '1:N', key: 'sales_site_name' },
		{ from: 'sectors', to: 'store_master', label: '1:N', key: 'sector_id' },
	];

	// File type categories
	function fileCategory(type: string | undefined): string {
		if (!type || type === 'unknown') return '—';
		if (type.startsWith('blackout')) return 'DAILY';
		if (['fuel_price','combo_sales','daily_sales','hourly_sales','store_master','site_mapping','sales'].includes(type)) return 'DAILY';
		if (type === 'sales_reference' || type === 'hourly_reference') return 'REFERENCE';
		if (type.startsWith('diesel_expense') || type === 'diesel_expense_ly') return 'REFERENCE';
		return 'UNKNOWN';
	}

	// Sync card quick preview
	let previewCard: string | null = $state(null);
	let previewData: any[] = $state([]);

	// Each card queries multiple tables to find data
	const PREVIEW_TABLES: Record<string, { tables: string[]; sector?: string }> = {
		blackout_cmhl: { tables: ['site_summary', 'daily_ops', 'generators', 'sites'], sector: 'CMHL' },
		blackout_cp: { tables: ['site_summary', 'daily_ops', 'generators', 'sites'], sector: 'CP' },
		blackout_cfc: { tables: ['site_summary', 'daily_ops', 'generators', 'sites'], sector: 'CFC' },
		blackout_pg: { tables: ['site_summary', 'daily_ops', 'generators', 'sites'], sector: 'PG' },
		fuel_price: { tables: ['fuel_prices'] },
		combo_sales: { tables: ['daily_sales', 'hourly_sales', 'store_master'] },
		diesel_expense_ly: { tables: ['uploads'] },
	};

	let previewTables: { name: string; rows: any[] }[] = $state([]);

	async function togglePreview(cardKey: string) {
		if (previewCard === cardKey) { previewCard = null; previewTables = []; return; }
		previewCard = cardKey;
		previewTables = [];
		const cfg = PREVIEW_TABLES[cardKey] || { tables: ['sites'] };
		const search = cfg.sector || '';

		for (const table of cfg.tables) {
			try {
				const res = await api.get(`/upload/raw/${table}?search=${search}`);
				const rows = (res.rows || []).slice(0, 10);
				if (rows.length > 0) {
					previewTables = [...previewTables, { name: table, rows }];
				}
			} catch { /* skip empty tables */ }
		}
	}

	function flash(msg: string, type: 'success'|'error' = 'success') { message = msg; messageType = type; setTimeout(() => message = '', 4000); }
	function fmt(v: number) { return v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(1)+'K' : v.toLocaleString(); }

	onMount(async () => { try { lastSync = await api.get('/upload/last-sync'); } catch {} loading = false; });

	async function switchTab(tab: string) {
		activeTab = tab;
		if (tab === 'summary') await loadSummary();
		else if (tab === 'raw') await loadRaw();
		else if (tab === 'history') await loadHistory();
		else if (tab === 'validation') await loadValidation();
	}

	// ─── Step 1: Validate files (no upload yet) ────────────
	async function handleFiles(files: FileList) {
		for (let i = 0; i < files.length; i++) {
			const file = files[i];
			if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
				queue = [...queue, { file, filename: file.name, size: file.size, status: 'INVALID', error: 'NOT_XLSX_FORMAT' }];
				continue;
			}
			const idx = queue.length;
			queue = [...queue, { file, filename: file.name, size: file.size, status: 'VALIDATING' }];
			validateFile(file, idx);
		}
	}

	const REF_TYPES = ['sales_reference', 'diesel_expense_ly', 'hourly_reference'];
	const DAILY_TYPES = ['fuel_price', 'combo_sales', 'daily_sales'];

	function isRefFile(t: string) { return REF_TYPES.includes(t) || t.startsWith('diesel_expense'); }
	function isDailyFile(t: string) { return t.startsWith('blackout') || DAILY_TYPES.includes(t); }

	async function validateFile(file: File, idx: number) {
		try {
			const formData = new FormData();
			formData.append('file', file);
			const token = localStorage.getItem('token');
			const res = await fetch('http://localhost:8000/api/upload/validate', {
				method: 'POST', headers: { 'Authorization': `Bearer ${token}` }, body: formData
			});
			if (!res.ok) { const e = await res.json(); throw new Error(e.detail); }
			const result = await res.json();
			const dt = result.type || '';
			const currentTab = uploadSection;

			// Tab-aware rejection: reference files on daily tab and vice versa
			if (currentTab === 'daily' && isRefFile(dt)) {
				queue = queue.map((q, i) => i === idx ? { ...q, status: 'WRONG_TAB' as const, type: dt, sheets: result.sheets, rows: result.rows, error: 'REFERENCE_FILE_ON_DAILY_TAB — Use REFERENCE_DATA tab', tab: currentTab } : q);
			} else if (currentTab === 'reference' && isDailyFile(dt)) {
				queue = queue.map((q, i) => i === idx ? { ...q, status: 'WRONG_TAB' as const, type: dt, sheets: result.sheets, rows: result.rows, error: 'DAILY_FILE_ON_REFERENCE_TAB — Use DAILY_DATA tab', tab: currentTab } : q);
			} else {
				queue = queue.map((q, i) => i === idx ? { ...q, status: 'VALIDATED' as const, type: dt, sheets: result.sheets, rows: result.rows, tab: currentTab } : q);
			}
		} catch (e: any) {
			queue = queue.map((q, i) => i === idx ? { ...q, status: 'INVALID' as const, error: e.message } : q);
		}
	}

	// ─── Step 2: Submit upload (user clicks button) ────────
	async function submitUpload() {
		const currentTab = activeTab;
		const validItems = queue.filter(q => q.status === 'VALIDATED' && q.tab === currentTab);
		if (validItems.length === 0) return flash('NO_VALID_FILES_TO_UPLOAD', 'error');
		submitting = true;

		// Start timer
		uploadProgress = { current: 0, total: validItems.length, filename: '', startTime: Date.now() };
		elapsed = 0;
		elapsedTimer = setInterval(() => { elapsed = Math.floor((Date.now() - uploadProgress.startTime) / 1000); }, 1000);

		let fileNum = 0;
		for (let i = 0; i < queue.length; i++) {
			if (queue[i].status !== 'VALIDATED' || queue[i].tab !== currentTab) continue;
			fileNum++;
			uploadProgress = { ...uploadProgress, current: fileNum, filename: queue[i].filename };
			queue = queue.map((q, j) => j === i ? { ...q, status: 'UPLOADING' as const } : q);

			try {
				const formData = new FormData();
				formData.append('file', queue[i].file);
				const token = localStorage.getItem('token');
				const controller = new AbortController();
				const timeoutId = setTimeout(() => controller.abort(), 600000); // 10 min timeout
				const res = await fetch('http://localhost:8000/api/upload', {
					method: 'POST', headers: { 'Authorization': `Bearer ${token}` }, body: formData,
					signal: controller.signal
				});
				clearTimeout(timeoutId);
				if (!res.ok) { const e = await res.json(); throw new Error(e.detail); }
				const result = await res.json();
				queue = queue.map((q, j) => j === i ? { ...q, status: 'IMPORTED' as const, type: result.type, rows: result.records, validation: result.validation || [] } : q);
			} catch (e: any) {
				queue = queue.map((q, j) => j === i ? { ...q, status: 'REJECTED' as const, error: e.message } : q);
			}
		}

		clearInterval(elapsedTimer);
		elapsedTimer = null;
		try { lastSync = await api.get('/upload/last-sync'); } catch {}
		submitting = false;
		const imported = queue.filter(q => q.status === 'IMPORTED').length;
		const rejected = queue.filter(q => q.status === 'REJECTED').length;
		flash(`COMPLETE: ${imported} IMPORTED, ${rejected} REJECTED`);
	}

	function onDrop(e: DragEvent) { e.preventDefault(); dragover = false; if (e.dataTransfer?.files) handleFiles(e.dataTransfer.files); }
	function onFileInput(e: Event) { const input = e.target as HTMLInputElement; if (input.files) handleFiles(input.files); input.value = ''; }
	function clearQueue() { queue = queue.filter(q => q.tab !== activeTab); }
	function removeFromQueue(idx: number) { queue = queue.filter((_, i) => i !== idx); }
	function removeByFilename(filename: string, tab: string) { queue = queue.filter(q => !(q.filename === filename && q.tab === tab)); }

	async function clearData(target: string) {
		try { await api.post(`/upload/clear/${target}`, {}); flash(`PURGED: ${target.toUpperCase()}`); lastSync = await api.get('/upload/last-sync'); }
		catch (e: any) { flash(e.message, 'error'); }
	}
	async function loadSummary() { try { const p = new URLSearchParams({ metric: summaryMetric }); if (summarySector) p.set('sector', summarySector); summaryData = await api.get(`/upload/store-summary?${p}`); } catch (e: any) { flash(e.message, 'error'); } }
	async function loadRaw() { try { const p = new URLSearchParams(); if (rawSearch) p.set('search', rawSearch); rawData = await api.get(`/upload/raw/${rawTable}?${p}`); } catch (e: any) { flash(e.message, 'error'); } }
	async function loadHistory() { try { history = await api.get('/upload/history'); } catch {} }

	const statusIcon: Record<string, string> = { VALIDATING: '🔄', VALIDATED: '✅', INVALID: '❌', WRONG_TAB: '⚠️', UPLOADING: '⏳', IMPORTED: '✅', REJECTED: '❌' };
	const statusColor: Record<string, string> = { VALIDATING: '#006f7c', VALIDATED: '#007518', INVALID: '#be2d06', WRONG_TAB: '#ff9d00', UPLOADING: '#ff9d00', IMPORTED: '#007518', REJECTED: '#be2d06' };

	function fmtSize(bytes: number): string {
		if (!bytes) return '—';
		if (bytes < 1024) return bytes + ' B';
		if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + ' KB';
		return (bytes / 1024 / 1024).toFixed(1) + ' MB';
	}


	function freshness(dateStr: string): { color: string; label: string } {
		if (!dateStr) return { color: '#65655e', label: 'NEVER' };
		const days = Math.floor((Date.now() - new Date(dateStr).getTime()) / 86400000);
		if (days <= 2) return { color: '#007518', label: `${days}d ago` };
		if (days <= 7) return { color: '#ff9d00', label: `${days}d ago` };
		return { color: '#be2d06', label: `${days}d ago` };
	}

	const tabQueue = $derived(queue.filter(q => q.tab === activeTab || (!q.tab && activeTab === 'daily')));
	const hasValidated = $derived(tabQueue.some(q => q.status === 'VALIDATED'));
	const hasAny = $derived(tabQueue.length > 0);
	const allDone = $derived(tabQueue.length > 0 && tabQueue.every(q => ['IMPORTED', 'REJECTED', 'INVALID', 'WRONG_TAB'].includes(q.status)));
</script>

{#if message}
	<div class="fixed top-20 right-6 z-50 px-4 py-3 text-sm font-bold uppercase tracking-wider" style="{messageType === 'success' ? 'background: #007518; color: white;' : 'background: #be2d06; color: white;'} border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">{message}</div>
{/if}

<div class="max-w-6xl mx-auto space-y-6">
	<!-- Header -->
	<div>
		<span class="inline-block px-3 py-1 mb-2 text-xs font-bold uppercase tracking-widest" style="background: #383832; color: #feffd6;">DATA_INGESTION_MODULE</span>
		<h1 class="text-4xl font-black uppercase tracking-tighter" style="border-bottom: 4px solid #383832; padding-bottom: 8px; color: #383832;">DATA_ENTRY</h1>
		<p class="text-sm font-medium mt-2 italic" style="color: #65655e;">Drop all files (daily + reference) together. System auto-classifies by sheet names.</p>
	</div>

	<!-- Tabs -->
	<div class="flex gap-0 overflow-x-auto" style="background: #ebe8dd; border: 2px solid #383832;">
		{#each tabs as tab}
			<button onclick={() => switchTab(tab.id)} class="px-3 py-2.5 font-bold uppercase tracking-tight text-[11px] whitespace-nowrap transition-all active:translate-x-[1px] active:translate-y-[1px]"
				style="{activeTab === tab.id ? 'background: #383832; color: #feffd6;' : 'background: transparent; color: #65655e;'}">{tab.label}</button>
		{/each}
	</div>

	<!-- ═══════════════════════════════════════════════════════ -->
	<!-- UPLOAD FILES -->
	<!-- ═══════════════════════════════════════════════════════ -->
	{#if activeTab === 'daily' || activeTab === 'reference'}

		{@const isDaily = activeTab === 'daily'}
		{@const accentColor = isDaily ? '#007518' : '#006f7c'}

		<!-- Section Header -->
		<div class="p-4" style="background: {accentColor}; color: white; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
			<div class="flex justify-between items-center">
				<div>
					<h2 class="text-lg font-black uppercase">{isDaily ? 'DAILY_DATA' : 'REFERENCE_DATA'}</h2>
					<p class="text-[10px] font-bold opacity-80 mt-0.5">{isDaily ? 'Upload every day — upserts by date+site, overwrites previous' : 'Upload once — historical baseline, batch insert for large files'}</p>
				</div>
			</div>
		</div>

		<!-- Accepted Files Table -->
		<div style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
			<div class="px-4 py-2 font-bold uppercase text-sm" style="background: #383832; color: #feffd6;">ACCEPTED_FILES</div>
			<div style="background: white;">
				<table class="w-full text-xs" style="border-collapse: collapse;">
					<thead style="background: #ebe8dd;">
						<tr>
							<th class="px-4 py-2 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">FILE</th>
							<th class="px-4 py-2 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">TYPE</th>
							<th class="px-4 py-2 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">DESCRIPTION</th>
							<th class="px-4 py-2 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">FREQUENCY</th>
							<th class="px-4 py-2 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">LAST_UPLOAD</th>
							<th class="px-4 py-2 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">ROWS</th>
						</tr>
					</thead>
					<tbody>
						{#if isDaily}
							{#each [
								{ file: 'Blackout Hr_ CFC.xlsx', type: 'blackout_cfc', desc: 'CFC generators, fuel, tank, blackout hours', freq: 'DAILY', icon: 'bakery_dining', syncKey: 'blackout_cfc' },
								{ file: 'Blackout Hr_ CMHL.xlsx', type: 'blackout_cmhl', desc: 'CMHL 31 stores, gen run hr, diesel used', freq: 'DAILY', icon: 'storefront', syncKey: 'blackout_cmhl' },
								{ file: 'Blackout Hr_ CP.xlsx', type: 'blackout_cp', desc: 'CP 25 sites, includes blackout hours', freq: 'DAILY', icon: 'apartment', syncKey: 'blackout_cp' },
								{ file: 'Blackout Hr_ PG.xlsx', type: 'blackout_pg', desc: 'PG sector distribution sites', freq: 'DAILY', icon: 'local_shipping', syncKey: 'blackout_pg' },
								{ file: 'Daily Fuel Price.xlsx', type: 'fuel_price', desc: 'Diesel prices from Denko/Moon Sun', freq: 'DAILY', icon: 'local_gas_station', syncKey: 'fuel_price' },
								{ file: 'CMHL_DAILY_SALES.xlsx', type: 'combo_sales', desc: 'Recent daily+hourly sales, store master', freq: 'DAILY', icon: 'point_of_sale', syncKey: 'combo_sales' },
							] as f, i}
								{@const fresh = freshness(lastSync[f.syncKey]?.synced_at)}
								<tr style="border-bottom: 1px solid rgba(56,56,50,0.15); {i % 2 ? 'background: #fcf9ef;' : ''}">
									<td class="px-4 py-2.5 font-bold flex items-center gap-2" style="color: #383832;">
										<span class="material-symbols-outlined text-sm" style="color: {accentColor};">{f.icon}</span> {f.file}
									</td>
									<td class="px-4 py-2.5 font-mono" style="color: {accentColor};">{f.type}</td>
									<td class="px-4 py-2.5" style="color: #65655e;">{f.desc}</td>
									<td class="px-4 py-2.5"><span class="px-2 py-0.5 text-[9px] font-bold" style="background: {accentColor}; color: white;">{f.freq}</span></td>
									<td class="px-4 py-2.5 text-[10px] font-mono">
										<span style="color: {lastSync[f.syncKey] ? '#383832' : '#be2d06'};">{lastSync[f.syncKey]?.synced_at || 'NEVER'}</span>
										<span class="ml-1.5 px-1.5 py-0.5 text-[9px] font-black" style="background: {fresh.color}; color: white;">{fresh.label}</span>
									</td>
									<td class="px-4 py-2.5 text-[10px] font-bold" style="color: #383832;">
										{lastSync[f.syncKey]?.rows?.toLocaleString() || '—'}
									</td>
								</tr>
							{/each}
						{:else}
							{#each [
								{ file: 'DailySales_1YearData.xlsx', type: 'sales_reference', desc: '126K+ daily sales + 570K hourly — 1 year history', freq: 'ONCE', icon: 'database', syncKey: 'combo_sales' },
								{ file: 'Daily Normal Diesel Expense.xlsx', type: 'diesel_expense_ly', desc: 'Last-year baseline expense per store', freq: 'ONCE', icon: 'history', syncKey: 'diesel_expense_ly' },
								{ file: 'Store Exp Percentage.xlsx', type: 'diesel_expense_ly', desc: 'Store-to-center expense mapping', freq: 'ONCE', icon: 'store', syncKey: 'diesel_expense_ly' },
							] as f, i}
								{@const fresh = freshness(lastSync[f.syncKey]?.synced_at)}
								<tr style="border-bottom: 1px solid rgba(56,56,50,0.15); {i % 2 ? 'background: #fcf9ef;' : ''}">
									<td class="px-4 py-2.5 font-bold flex items-center gap-2" style="color: #383832;">
										<span class="material-symbols-outlined text-sm" style="color: {accentColor};">{f.icon}</span> {f.file}
									</td>
									<td class="px-4 py-2.5 font-mono" style="color: {accentColor};">{f.type}</td>
									<td class="px-4 py-2.5" style="color: #65655e;">{f.desc}</td>
									<td class="px-4 py-2.5"><span class="px-2 py-0.5 text-[9px] font-bold" style="background: {accentColor}; color: white;">{f.freq}</span></td>
									<td class="px-4 py-2.5 text-[10px] font-mono">
										<span style="color: {lastSync[f.syncKey] ? '#383832' : '#be2d06'};">{lastSync[f.syncKey]?.synced_at || 'NEVER'}</span>
										<span class="ml-1.5 px-1.5 py-0.5 text-[9px] font-black" style="background: {fresh.color}; color: white;">{fresh.label}</span>
									</td>
									<td class="px-4 py-2.5 text-[10px] font-bold" style="color: #383832;">
										{lastSync[f.syncKey]?.rows?.toLocaleString() || '—'}
									</td>
								</tr>
							{/each}
						{/if}
					</tbody>
				</table>
			</div>
		</div>

		<!-- Drop Zone -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="p-10 text-center cursor-pointer transition-all"
			style="background: {dragover ? '#ebe8dd' : 'white'}; border: 3px dashed {dragover ? accentColor : '#383832'};"
			ondragover={(e) => { e.preventDefault(); uploadSection = activeTab; dragover = true; }}
			ondragleave={() => dragover = false}
			ondrop={(e) => { uploadSection = activeTab; onDrop(e); }}
			onclick={() => { uploadSection = activeTab; document.getElementById('file-input-' + activeTab)?.click(); }}>
			<span class="material-symbols-outlined text-4xl" style="color: {accentColor};">cloud_upload</span>
			<p class="text-sm font-black uppercase mt-2" style="color: #383832;">DROP_{isDaily ? 'DAILY' : 'REFERENCE'}_FILES_HERE</p>
			<p class="text-[10px] font-bold uppercase mt-1" style="color: #65655e;">
				{isDaily ? 'Blackout, fuel price, recent sales — overwrites by date+site' : '1-year sales, LY expense — batch insert, upload once'}
			</p>
			<input id="file-input-{activeTab}" type="file" accept=".xlsx,.xls" multiple class="hidden" onchange={(e) => { uploadSection = activeTab; onFileInput(e); }} />
		</div>

		<!-- Processing Queue -->
		{#if hasAny}
			<div style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
				<div class="px-4 py-2 flex justify-between items-center" style="background: #383832; color: #feffd6;">
					<span class="font-bold uppercase tracking-widest text-sm">VALIDATION_QUEUE — {tabQueue.length} FILE{tabQueue.length > 1 ? 'S' : ''}</span>
					<button onclick={clearQueue} class="text-[10px] font-bold uppercase underline decoration-2 underline-offset-4" style="color: #fe97b9;">CLEAR</button>
				</div>
				<div style="background: white;">
					<table class="w-full text-xs font-mono" style="border-collapse: collapse;">
						<thead style="background: #ebe8dd;">
							<tr>
								<th class="px-4 py-2 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">FILE</th>
								<th class="px-4 py-2 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">DETECTED_TYPE</th>
								<th class="px-4 py-2 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">CATEGORY</th>
								<th class="px-4 py-2 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">ROWS</th>
								<th class="px-4 py-2 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">SIZE</th>
								<th class="px-4 py-2 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">STATUS</th>
								<th class="px-4 py-2 text-left font-black uppercase" style="border-bottom: 2px solid #383832;"></th>
							</tr>
						</thead>
						<tbody>
							{#each tabQueue as item, i}
								<tr style="border-bottom: 1px solid rgba(56,56,50,0.15); {i % 2 ? 'background: #fcf9ef;' : ''}">
									<td class="px-4 py-3 font-bold truncate max-w-[200px]" style="color: #383832;">{item.filename}</td>
									<td class="px-4 py-3" style="color: #006f7c;">{item.type || '—'}</td>
									<td class="px-4 py-3">
										{#if item.type}
											<span class="px-2 py-0.5 text-[9px] font-bold uppercase" style="background: {fileCategory(item.type) === 'DAILY' ? '#007518' : fileCategory(item.type) === 'REFERENCE' ? '#006f7c' : '#828179'}; color: white;">
												{fileCategory(item.type)}
											</span>
										{:else}
											<span style="color: #828179;">—</span>
										{/if}
									</td>
									<td class="px-4 py-3" style="color: #383832;">{typeof item.rows === 'number' ? item.rows.toLocaleString() : '—'}</td>
									<td class="px-4 py-3" style="color: #65655e;">{fmtSize(item.size)}</td>
									<td class="px-4 py-3">
										<span class="inline-flex items-center gap-1 px-2 py-0.5 font-bold uppercase text-[10px]" style="background: {statusColor[item.status]}; color: white;">
											{statusIcon[item.status]} {item.status}
										</span>
										{#if item.error}<span class="text-[9px] ml-2" style="color: {item.status === 'WRONG_TAB' ? '#ff9d00' : '#be2d06'};">{item.error}</span>{/if}
										{#if item.status === 'VALIDATING' || item.status === 'UPLOADING'}<span class="animate-pulse ml-1">...</span>{/if}
									</td>
									<td class="px-4 py-3">
										{#if item.status === 'VALIDATED' || item.status === 'INVALID' || item.status === 'WRONG_TAB'}
											<button onclick={() => removeByFilename(item.filename, item.tab || activeTab)} class="text-[9px] font-bold uppercase" style="color: #be2d06;">✕</button>
										{/if}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>

				<!-- Validation Table: Excel vs Pipeline vs DB -->
				{#each tabQueue.filter(q => q.status === 'IMPORTED' && q.validation && q.validation.length > 0) as item}
					{@const allPass = item.validation.every((v: any) => v.pass)}
					{@const passCount = item.validation.filter((v: any) => v.pass).length}
					{@const fmtN = (v: number) => v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(1)+'K' : Math.round(v).toLocaleString()}
					<div class="mt-2" style="border: 2px solid {allPass ? '#007518' : '#ff9d00'};">
						<div class="px-4 py-2 flex justify-between items-center" style="background: {allPass ? '#007518' : '#ff9d00'}; color: white;">
							<span class="font-black uppercase text-xs">DATA QUALITY — {item.filename} — {item.type?.toUpperCase()}</span>
							<span class="text-[10px] font-bold">{passCount}/{item.validation.length} DATES PASS {allPass ? '✓' : ''}</span>
						</div>
						<div class="overflow-x-auto" style="max-height: 300px; overflow-y: auto;">
							<table class="w-full text-[10px] font-mono">
								<thead>
									<tr style="background: #ebe8dd; position: sticky; top: 0;">
										<th class="px-2 py-1.5 text-left font-black" style="border-bottom: 2px solid #383832;">DATE</th>
										<th class="px-2 py-1.5 text-center font-black">SITES</th>
										<th class="px-2 py-1.5 text-center font-black" style="color: #006f7c;">GEN HR<br/>EXCEL</th>
										<th class="px-2 py-1.5 text-center font-black" style="color: #006f7c;">GEN HR<br/>DB</th>
										<th class="px-2 py-1.5 text-center font-black" style="color: #e85d04;">FUEL<br/>EXCEL</th>
										<th class="px-2 py-1.5 text-center font-black" style="color: #e85d04;">FUEL<br/>DB</th>
										<th class="px-2 py-1.5 text-center font-black" style="color: #007518;">TANK<br/>EXCEL</th>
										<th class="px-2 py-1.5 text-center font-black" style="color: #007518;">TANK<br/>DB</th>
										<th class="px-2 py-1.5 text-center font-black" style="color: #be2d06;">BO<br/>EXCEL</th>
										<th class="px-2 py-1.5 text-center font-black" style="color: #be2d06;">BO<br/>DB</th>
										<th class="px-2 py-1.5 text-center font-black">STATUS</th>
									</tr>
								</thead>
								<tbody>
									{#each item.validation as v, vi}
										<tr style="background: {vi % 2 ? '#f6f4e9' : 'white'}; border-bottom: 1px solid #ebe8dd;">
											<td class="px-2 py-1 font-bold">{v.date}</td>
											<td class="px-2 py-1 text-center">{v.sites}</td>
											<td class="px-2 py-1 text-center">{fmtN(v.excel.gen_hr)}</td>
											<td class="px-2 py-1 text-center" style="background: {Math.abs(v.excel.gen_hr - v.db.gen_hr) < 2 ? '#C6EFCE' : '#FFC7CE'};">{fmtN(v.db.gen_hr)}</td>
											<td class="px-2 py-1 text-center">{fmtN(v.excel.fuel)}</td>
											<td class="px-2 py-1 text-center" style="background: {Math.abs(v.excel.fuel - v.db.fuel) < 2 ? '#C6EFCE' : '#FFC7CE'};">{fmtN(v.db.fuel)}</td>
											<td class="px-2 py-1 text-center">{fmtN(v.excel.tank)}</td>
											<td class="px-2 py-1 text-center" style="background: {Math.abs(v.excel.tank - v.db.tank) < 2 ? '#C6EFCE' : '#FFC7CE'};">{fmtN(v.db.tank)}</td>
											<td class="px-2 py-1 text-center">{v.excel.blackout.toFixed(1)}</td>
											<td class="px-2 py-1 text-center" style="background: {Math.abs(v.excel.blackout - v.db.blackout) < 2 ? '#C6EFCE' : '#FFC7CE'};">{v.db.blackout.toFixed(1)}</td>
											<td class="px-2 py-1 text-center font-black" style="color: {v.pass ? '#007518' : '#be2d06'};">{v.pass ? '✓ PASS' : '✗ FAIL'}</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					</div>
				{/each}

				<!-- Submit Button -->
				<div class="p-4 flex justify-between items-center" style="background: #ebe8dd; border-top: 2px solid #383832;">
					<div class="text-[10px] font-bold uppercase" style="color: #65655e;">
						{tabQueue.filter(q => q.status === 'VALIDATED').length} READY
						{#if tabQueue.filter(q => q.status === 'INVALID').length > 0}
							 · {tabQueue.filter(q => q.status === 'INVALID').length} INVALID
						{/if}
						{#if tabQueue.filter(q => q.status === 'WRONG_TAB').length > 0}
							 · <span style="color: #ff9d00;">{tabQueue.filter(q => q.status === 'WRONG_TAB').length} WRONG_TAB</span>
						{/if}
						{#if allDone}
							 · ALL_PROCESSED
						{/if}
					</div>
					{#if hasValidated && !submitting}
						<button onclick={submitUpload}
							class="px-8 py-3 font-black uppercase text-sm active:translate-x-[2px] active:translate-y-[2px]"
							style="background: #00fc40; color: #383832; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
							SUBMIT_UPLOAD ({tabQueue.filter(q => q.status === 'VALIDATED').length} FILES)
						</button>
					{:else if submitting}
						<div class="flex-1 mr-4">
							<!-- Progress bar -->
							<div class="flex items-center gap-3 mb-1">
								<div class="text-[10px] font-black uppercase" style="color: #383832;">
									PROCESSING {uploadProgress.current}/{uploadProgress.total}
								</div>
								<div class="text-[10px] font-mono" style="color: #65655e;">
									{Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, '0')} elapsed
								</div>
							</div>
							<div class="w-full h-3 overflow-hidden" style="background: #ebe8dd; border: 1px solid #383832;">
								<div class="h-full transition-all" style="background: #00fc40; width: {uploadProgress.total > 0 ? (uploadProgress.current / uploadProgress.total * 100) : 0}%;"></div>
							</div>
							<div class="text-[9px] font-mono mt-1 truncate" style="color: #ff9d00;">
								{uploadProgress.filename} — please wait, large files may take several minutes...
							</div>
						</div>
						<div class="px-6 py-3 font-black uppercase text-sm animate-pulse shrink-0" style="background: #ff9d00; color: #383832; border: 2px solid #383832;">
							UPLOADING...
						</div>
					{/if}
				</div>
			</div>
		{/if}

		<!-- Last Sync Status (clickable cards) -->
		<div>
			<h3 class="text-sm font-black uppercase mb-3" style="color: #383832; border-bottom: 2px solid #383832; padding-bottom: 4px;">SYNC_STATUS — CLICK_FOR_PREVIEW</h3>
			<div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
				{#each SYNC_CARDS as card}
					{@const sync = lastSync[card.key]}
					{@const fresh = freshness(sync?.synced_at)}
					<button onclick={() => togglePreview(card.key)}
						class="p-3 text-left transition-all active:translate-x-[1px] active:translate-y-[1px]"
						style="border: 2px solid {previewCard === card.key ? '#007518' : '#383832'}; background: {sync ? '#f6f4e9' : 'white'}; box-shadow: 3px 3px 0px 0px #383832; {previewCard === card.key ? 'outline: 2px solid #007518;' : ''}">
						<div class="flex items-center justify-between mb-2">
							<span class="material-symbols-outlined text-sm" style="color: {sync ? '#007518' : '#be2d06'};">{card.icon}</span>
							<span class="w-2 h-2" style="background: {fresh.color};"></span>
						</div>
						<div class="text-[10px] font-black uppercase" style="color: #383832;">{card.label}</div>
						{#if sync}
							<div class="text-[9px] font-bold mt-1" style="color: #007518;">{sync.rows?.toLocaleString()} ROWS</div>
							<div class="text-[8px] font-bold" style="color: #65655e;">{sync.synced_at}</div>
							<div class="mt-1 px-1.5 py-0.5 text-[8px] font-black text-center" style="background: {fresh.color}; color: white;">{fresh.label}</div>
						{:else}
							<div class="text-[9px] font-bold mt-1" style="color: #be2d06;">NO_DATA</div>
						{/if}
					</button>
				{/each}
			</div>

			<!-- Quick Preview Tables -->
			{#if previewCard && previewTables.length > 0}
				<div class="mt-3 space-y-3">
					{#each previewTables as pt}
						<div style="border: 2px solid #007518; box-shadow: 4px 4px 0px 0px #383832;">
							<div class="px-4 py-2 flex justify-between items-center" style="background: #007518; color: white;">
								<span class="font-bold uppercase text-sm">{pt.name.toUpperCase()} — {pt.rows.length} ROWS</span>
								{#if pt === previewTables[0]}
									<button onclick={() => { previewCard = null; previewTables = []; }} class="text-xs font-bold">✕ CLOSE</button>
								{/if}
							</div>
							<div class="overflow-x-auto max-h-[200px] overflow-y-auto" style="background: white;">
								<table class="text-[10px] w-full font-mono" style="border-collapse: collapse;">
									<thead class="sticky top-0" style="background: #ebe8dd;">
										<tr>{#each Object.keys(pt.rows[0]) as col}<th class="px-2 py-1.5 text-left font-black uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">{col}</th>{/each}</tr>
									</thead>
									<tbody>
										{#each pt.rows as row, i}
											<tr style="border-bottom: 1px solid rgba(56,56,50,0.15); {i % 2 ? 'background: #fcf9ef;' : ''}">
												{#each Object.values(row) as val}<td class="px-2 py-1 whitespace-nowrap max-w-[180px] truncate" style="color: #383832;">{val ?? '—'}</td>{/each}
											</tr>
										{/each}
									</tbody>
								</table>
							</div>
						</div>
					{/each}
					<div class="px-4 py-1 text-[9px] font-bold uppercase text-center" style="color: #65655e;">SHOWING_FIRST_10_ROWS_PER_TABLE — GO_TO_RAW_DATA_TAB_FOR_FULL_VIEW</div>
				</div>
			{:else if previewCard}
				<div class="mt-3 p-4 text-center text-xs font-bold uppercase" style="border: 2px solid #383832; background: white; color: #65655e;">NO_DATA_FOR_{previewCard?.toUpperCase()}</div>
			{/if}
		</div>

	<!-- Other tabs (same as before) -->
	{:else if activeTab === 'summary'}
		<div class="flex gap-3 mb-4">
			<div class="flex-1"><div class="inline-block px-2 py-0.5 text-[9px] font-black uppercase mb-1" style="background: #383832; color: #feffd6;">SECTOR</div>
				<select bind:value={summarySector} onchange={loadSummary} class="w-full px-3 py-2 text-sm font-bold uppercase" style="background: white; border: 2px solid #383832; color: #383832;"><option value="">ALL</option><option value="CMHL">CMHL</option><option value="CP">CP</option><option value="CFC">CFC</option><option value="PG">PG</option></select></div>
			<div class="flex-[2]"><div class="inline-block px-2 py-0.5 text-[9px] font-black uppercase mb-1" style="background: #383832; color: #feffd6;">METRIC</div>
				<select bind:value={summaryMetric} onchange={loadSummary} class="w-full px-3 py-2 text-sm font-bold uppercase" style="background: white; border: 2px solid #383832; color: #383832;">{#each METRICS as m}<option value={m.key}>{m.label}</option>{/each}</select></div>
		</div>
		{#if summaryData?.pivot?.length > 0}
			<div style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;"><div class="px-4 py-2 flex justify-between" style="background: #383832; color: #feffd6;"><span class="font-bold uppercase text-sm">{summaryData.metric_label}</span><span class="text-[10px]">{summaryData.sites?.length}x{summaryData.dates?.length}</span></div>
			<div class="overflow-x-auto max-h-[500px] overflow-y-auto" style="background: white;"><table class="text-[10px] w-full font-mono" style="border-collapse: collapse;"><thead class="sticky top-0" style="background: #ebe8dd;"><tr><th class="px-2 py-1.5 text-left font-black uppercase sticky left-0" style="background: #ebe8dd; border-right: 2px solid #383832;">SITE</th><th class="px-2 py-1.5 text-left font-black uppercase sticky left-[80px]" style="background: #ebe8dd; border-right: 2px solid #383832;">SEC</th>{#each summaryData.dates as d}<th class="px-2 py-1.5 text-right font-bold" style="border-bottom: 2px solid #383832;">{d.slice(5)}</th>{/each}</tr></thead>
			<tbody>{#each summaryData.pivot as row, i}<tr style="border-bottom: 1px solid rgba(56,56,50,0.15); {i % 2 ? 'background: #fcf9ef;' : ''}"><td class="px-2 py-1 font-bold sticky left-0" style="{i%2?'background:#fcf9ef;':'background:white;'} border-right: 2px solid #383832; color: #383832;">{row.site_id}</td><td class="px-2 py-1 sticky left-[80px]" style="{i%2?'background:#fcf9ef;':'background:white;'} border-right: 2px solid #383832; color: #65655e;">{row.sector_id}</td>{#each summaryData.dates as d}{@const v=row[d]}<td class="px-2 py-1 text-right" style="color:{summaryMetric==='days_of_buffer'&&v!==null?(v<3?'#be2d06':v<7?'#ff9d00':'#007518'):'#383832'};">{v!==null&&v!==''?(typeof v==='number'?v.toLocaleString(undefined,{maximumFractionDigits:1}):v):'—'}</td>{/each}</tr>{/each}</tbody></table></div></div>
		{:else}<div class="p-8 text-center font-bold uppercase" style="background: #f6f4e9; border: 2px solid #383832; color: #65655e;">NO_DATA</div>{/if}

	{:else if activeTab === 'raw'}
		<div class="flex flex-wrap gap-0 mb-4" style="background: #ebe8dd; border: 2px solid #383832;">{#each RAW_TABLES as t}<button onclick={() => { rawTable = t.key; rawSearch = ''; loadRaw(); }} class="px-3 py-2 text-[10px] font-bold uppercase" style="{rawTable === t.key ? 'background: #383832; color: #feffd6;' : 'color: #65655e;'}">{t.label}</button>{/each}</div>
		<div class="flex gap-3 mb-4"><div class="flex-1"><div class="inline-block px-2 py-0.5 text-[9px] font-black uppercase mb-1" style="background: #383832; color: #feffd6;">SEARCH</div><input bind:value={rawSearch} placeholder="QUERY..." onkeydown={(e) => { if ((e as KeyboardEvent).key === 'Enter') loadRaw(); }} class="w-full px-3 py-2 text-sm font-bold uppercase" style="background: white; border: 2px solid #383832; color: #383832;" /></div><div class="self-end"><button onclick={loadRaw} class="px-4 py-2 text-sm font-black uppercase active:translate-x-[1px] active:translate-y-[1px]" style="background: #007518; color: white; border: 2px solid #383832;">EXECUTE</button></div></div>
		<div style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;"><div class="px-4 py-2 flex justify-between" style="background: #383832; color: #feffd6;"><span class="font-bold uppercase text-sm">{rawTable.toUpperCase()}</span><span class="text-[10px]">{rawData.count} ROWS</span></div>
		{#if rawData.rows.length > 0}<div class="overflow-x-auto max-h-[500px] overflow-y-auto" style="background: white;"><table class="text-[10px] w-full font-mono" style="border-collapse: collapse;"><thead class="sticky top-0" style="background: #ebe8dd;"><tr>{#each Object.keys(rawData.rows[0]) as col}<th class="px-2 py-1.5 text-left font-black uppercase whitespace-nowrap" style="border-bottom: 2px solid #383832;">{col}</th>{/each}</tr></thead><tbody>{#each rawData.rows as row, i}<tr style="border-bottom: 1px solid rgba(56,56,50,0.15); {i%2?'background:#fcf9ef;':''};">{#each Object.values(row) as val}<td class="px-2 py-1 whitespace-nowrap max-w-[200px] truncate" style="color: #383832;">{val ?? '—'}</td>{/each}</tr>{/each}</tbody></table></div>{:else}<div class="p-6 text-center font-bold uppercase" style="background: white; color: #65655e;">EMPTY</div>{/if}</div>

	{:else if activeTab === 'validation'}
		{#if validationLoading}
			<div class="p-8 text-center font-bold uppercase" style="background: white; border: 2px solid #383832; color: #65655e;">LOADING...</div>
		{:else if validationData && validationData.sectors}
			{@const fmtN = (v: number) => v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(1)+'K' : Math.round(v).toLocaleString()}
			<!-- Summary cards -->
			<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
				{#each validationData.sectors as sec}
					{@const allPass = sec.rows.every((r: any) => r.pass)}
					<div class="p-4 text-center" style="border: 2px solid {allPass ? '#007518' : '#be2d06'}; background: white; box-shadow: 4px 4px 0px 0px #383832;">
						<div class="text-2xl font-black" style="color: {allPass ? '#007518' : '#be2d06'};">{sec.sector}</div>
						<div class="text-[10px] font-bold uppercase mt-1" style="color: #65655e;">{sec.rows.filter((r: any) => r.pass).length}/{sec.rows.length} DATES PASS</div>
						<div class="text-xs font-black mt-1" style="color: {allPass ? '#007518' : '#be2d06'};">{allPass ? '✓ ALL MATCH' : '✗ HAS DIFF'}</div>
					</div>
				{/each}
			</div>

			<!-- Per-sector tables -->
			{#each validationData.sectors as sec}
				{@const allPass = sec.rows.every((r: any) => r.pass)}
				{@const passCount = sec.rows.filter((r: any) => r.pass).length}
				<div class="mb-4" style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
					<div class="px-4 py-2 flex justify-between items-center" style="background: {allPass ? '#007518' : '#ff9d00'}; color: white;">
						<span class="font-black uppercase text-sm">{sec.sector} — DATA QUALITY</span>
						<span class="text-[10px] font-bold">{sec.sites} sites | {sec.generators} gens | {passCount}/{sec.rows.length} PASS {allPass ? '✓' : ''}</span>
					</div>
					<div class="overflow-x-auto" style="max-height: 350px; overflow-y: auto;">
						<table class="w-full text-[10px] font-mono" style="border-collapse: collapse;">
							<thead>
								<tr style="background: #ebe8dd; position: sticky; top: 0; z-index: 1;">
									<th class="px-2 py-1.5 text-left font-black" style="border-bottom: 2px solid #383832;">DATE</th>
									<th class="px-2 py-1.5 text-center font-black">SITES</th>
									<th class="px-2 py-1.5 text-center font-black" style="color: #006f7c;">GEN HR<br/>EXCEL</th>
									<th class="px-2 py-1.5 text-center font-black" style="color: #006f7c;">GEN HR<br/>DB</th>
									<th class="px-2 py-1.5 text-center font-black" style="color: #e85d04;">FUEL<br/>EXCEL</th>
									<th class="px-2 py-1.5 text-center font-black" style="color: #e85d04;">FUEL<br/>DB</th>
									<th class="px-2 py-1.5 text-center font-black" style="color: #007518;">TANK<br/>EXCEL</th>
									<th class="px-2 py-1.5 text-center font-black" style="color: #007518;">TANK<br/>DB</th>
									<th class="px-2 py-1.5 text-center font-black" style="color: #be2d06;">BO<br/>EXCEL</th>
									<th class="px-2 py-1.5 text-center font-black" style="color: #be2d06;">BO<br/>DB</th>
									<th class="px-2 py-1.5 text-center font-black">STATUS</th>
								</tr>
							</thead>
							<tbody>
								{#each sec.rows as v, vi}
									<tr style="background: {vi % 2 ? '#f6f4e9' : 'white'}; border-bottom: 1px solid #ebe8dd;">
										<td class="px-2 py-1 font-bold">{v.date}</td>
										<td class="px-2 py-1 text-center">{v.sites}</td>
										<td class="px-2 py-1 text-center">{fmtN(v.excel.gen_hr)}</td>
										<td class="px-2 py-1 text-center" style="background: {Math.abs(v.excel.gen_hr - v.db.gen_hr) < 2 ? '#C6EFCE' : '#FFC7CE'};">{fmtN(v.db.gen_hr)}</td>
										<td class="px-2 py-1 text-center">{fmtN(v.excel.fuel)}</td>
										<td class="px-2 py-1 text-center" style="background: {Math.abs(v.excel.fuel - v.db.fuel) < 2 ? '#C6EFCE' : '#FFC7CE'};">{fmtN(v.db.fuel)}</td>
										<td class="px-2 py-1 text-center">{fmtN(v.excel.tank)}</td>
										<td class="px-2 py-1 text-center" style="background: {Math.abs(v.excel.tank - v.db.tank) < 2 ? '#C6EFCE' : '#FFC7CE'};">{fmtN(v.db.tank)}</td>
										<td class="px-2 py-1 text-center">{v.excel.blackout.toFixed(1)}</td>
										<td class="px-2 py-1 text-center" style="background: {Math.abs(v.excel.blackout - v.db.blackout) < 2 ? '#C6EFCE' : v.bo_issue ? '#FFF3CD' : '#FFC7CE'};">{v.db.blackout.toFixed(1)}</td>
										<td class="px-2 py-1 text-center font-black" style="color: {v.pass ? '#007518' : '#be2d06'};">{v.pass ? '✓' : '✗'}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
					<div class="px-4 py-1.5 text-[9px] font-mono" style="background: #f6f4e9; color: #65655e; border-top: 1px solid #ebe8dd;">
						Pipeline: GenHr=SUM(all gens) | Fuel=SUM(all gens) | Tank=SUM(all gens) | Blackout=SUM(first row/site)
					</div>

					<!-- Issues -->
					{#if sec.issues && sec.issues.length > 0}
						<div class="px-4 py-2" style="background: #fff3cd; border-top: 2px solid #ff9d00;">
							<div class="text-[10px] font-black uppercase mb-2" style="color: #856404;">EXCEL ISSUES FOUND — {sec.issues.length} problem{sec.issues.length > 1 ? 's' : ''}</div>
							<table class="w-full text-[10px]" style="border-collapse: collapse;">
								<thead>
									<tr style="background: rgba(255,157,0,0.15);">
										<th class="px-2 py-1 text-left font-black" style="border-bottom: 1px solid #ff9d00;">TYPE</th>
										<th class="px-2 py-1 text-left font-black" style="border-bottom: 1px solid #ff9d00;">COLUMN</th>
										<th class="px-2 py-1 text-left font-black" style="border-bottom: 1px solid #ff9d00;">SITE</th>
										<th class="px-2 py-1 text-left font-black" style="border-bottom: 1px solid #ff9d00;">ISSUE</th>
									</tr>
								</thead>
								<tbody>
									{#each sec.issues as issue, ii}
										<tr style="background: {ii % 2 ? 'rgba(255,157,0,0.05)' : 'white'}; border-bottom: 1px solid #ebe8dd;">
											<td class="px-2 py-1">
												<span class="px-1.5 py-0.5 text-[8px] font-black uppercase" style="background: {issue.type === 'TIME_FORMAT' ? '#be2d06' : '#ff9d00'}; color: white;">
													{issue.type === 'TIME_FORMAT' ? 'TIME FMT' : 'NO FORMULA'}
												</span>
											</td>
											<td class="px-2 py-1 font-bold" style="color: #383832;">{issue.col}</td>
											<td class="px-2 py-1 font-mono" style="color: #006f7c;">
												{#if issue.site_id}{issue.site_name} <span style="color: #828179;">({issue.site_id})</span>{:else}—{/if}
											</td>
											<td class="px-2 py-1" style="color: #856404;">{issue.msg}</td>
										</tr>
									{/each}
								</tbody>
							</table>
							<div class="mt-2 text-[9px] font-bold" style="color: #856404;">
								Pipeline reads correct values. Fix these in the Excel file for accurate totals.
							</div>
						</div>
					{/if}
				</div>
			{/each}
		{:else}
			<div class="p-8 text-center font-bold uppercase" style="background: white; border: 2px solid #383832; color: #65655e;">NO DATA — Upload blackout files first</div>
		{/if}

	{:else if activeTab === 'cleaning'}
		<div class="space-y-6">
			{#each [{title:'FILE_DETECTION',sub:'By sheet names',rows:[['Sheet "CP"','BLACKOUT_CP'],['Sheet "CMHL"','BLACKOUT_CMHL'],['Sheet "CFC"','BLACKOUT_CFC'],['Sheet "PG"','BLACKOUT_PG'],['Multiple sectors','FUEL_PRICE'],['"daily sales"+"hourly"','COMBO_SALES'],['Daily Average Diesel','LY_EXPENSE']]},{title:'NAME_FIX',sub:'Generator typos',rows:[['KHOLER-550','KOHLER-550'],['HIMONISA-200','HIMOINSA-200'],['550 KVA - G1','550KVA-G1']]},{title:'VALUE_CLEAN',sub:'Messy data',rows:[['-','NULL'],['X','NULL'],['#DIV/0!','NULL'],['5614 (blackout)','REJECTED']]}] as s}
				<div style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;"><div class="px-4 py-2 font-bold uppercase text-sm" style="background: #383832; color: #feffd6;">{s.title}</div><div class="px-4 py-1 text-[10px] font-bold uppercase" style="background: #ebe8dd; color: #65655e;">{s.sub}</div><div style="background: white;">{#each s.rows as [from, to], i}<div class="flex px-4 py-2 text-xs font-bold" style="border-bottom: 1px solid rgba(56,56,50,0.15); {i%2?'background:#fcf9ef;':''}"><span class="flex-1 font-mono" style="color: #be2d06;">{from}</span><span class="px-2" style="color: #65655e;">→</span><span class="flex-1 font-mono" style="color: #007518;">{to}</span></div>{/each}</div></div>
			{/each}
		</div>

	{:else if activeTab === 'history'}
		{#if history.totals}<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">{#each [{l:'SITES',k:'sites'},{l:'GENS',k:'generators'},{l:'OPS',k:'daily_operations'},{l:'FUEL',k:'fuel_purchases'},{l:'SALES',k:'daily_sales'},{l:'HOURLY',k:'hourly_sales'},{l:'STORES',k:'store_master'},{l:'LY_EXP',k:'diesel_expense_ly'}] as t}<div class="p-4 text-center" style="border: 2px solid #383832; background: white; box-shadow: 4px 4px 0px 0px #383832;"><div class="text-[9px] font-black uppercase opacity-60">{t.l}</div><div class="text-2xl font-black" style="color: #383832;">{fmt(history.totals[t.k]||0)}</div></div>{/each}</div>{/if}
		{#if history.uploads?.length > 0}<div style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;"><div class="px-4 py-2 font-bold uppercase text-sm" style="background: #383832; color: #feffd6;">UPLOAD_LOG</div><div class="overflow-x-auto" style="background: white;"><table class="text-xs w-full font-mono" style="border-collapse: collapse;"><thead style="background: #ebe8dd;"><tr>{#each ['FILE','TYPE','SEC','PARSED','OK','FAIL','TIME'] as c}<th class="px-3 py-2 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">{c}</th>{/each}</tr></thead><tbody>{#each history.uploads as u, i}<tr style="border-bottom: 1px solid rgba(56,56,50,0.15); {i%2?'background:#fcf9ef;':''}"><td class="px-3 py-2 font-bold truncate max-w-[180px]" style="color: #383832;">{u.filename}</td><td class="px-3 py-2" style="color: #006f7c;">{u.file_type}</td><td class="px-3 py-2" style="color: #65655e;">{u.sector_id||'—'}</td><td class="px-3 py-2">{u.rows_parsed?.toLocaleString()}</td><td class="px-3 py-2" style="color: #007518;">{u.rows_accepted?.toLocaleString()}</td><td class="px-3 py-2" style="color: {u.rows_rejected>0?'#be2d06':'#65655e'};">{u.rows_rejected||0}</td><td class="px-3 py-2" style="color: #65655e;">{u.uploaded_at?.slice(0,16)}</td></tr>{/each}</tbody></table></div></div>{:else}<div class="p-8 text-center font-bold uppercase" style="background: #f6f4e9; border: 2px solid #383832; color: #65655e;">NO_UPLOADS</div>{/if}

	{:else if activeTab === 'model'}
		{@const erdTables = [
			{ name: 'sites', color: '#383832', cols: [
				['site_id','TEXT','PK',''],['site_name','TEXT','',''],['sector_id','TEXT','FK','→ sectors.sector_id'],
				['site_type','TEXT','','Regular/LNG'],['cost_center_code','TEXT','FK*','UNIVERSAL JOIN KEY'],
				['business_sector','TEXT','',''],['company','TEXT','',''],
				['latitude','REAL','','from store_master'],['longitude','REAL','','from store_master'],
				['address_state','TEXT','','from store_master'],['address_township','TEXT','','from store_master'],
				['store_size','TEXT','','S/M/L/XL'],['channel','TEXT','','Retail/F&B'],
				['gold_code','TEXT','','POS system ID'],['manager','TEXT','','person responsible'],
			]},
			{ name: 'generators', color: '#383832', cols: [
				['generator_id','INT','PK','AUTO'],['site_id','TEXT','FK','→ sites.site_id'],
				['model_name','TEXT','','canonical'],['power_kva','REAL','',''],
				['consumption_per_hour','REAL','','rated L/Hr'],['fuel_type','TEXT','',''],['supplier','TEXT','','']
			]},
			{ name: 'daily_operations', color: '#006f7c', cols: [
				['id','INT','PK',''],['generator_id','INT','FK','→ generators'],
				['site_id','TEXT','FK','→ sites'],['date','TEXT','UK',''],
				['gen_run_hr','REAL','','hours'],['daily_used_liters','REAL','','liters'],
				['spare_tank_balance','REAL','','liters'],['blackout_hr','REAL','','hours']
			]},
			{ name: 'daily_site_summary', color: '#9d4867', cols: [
				['site_id','TEXT','PK+FK','→ sites'],['date','TEXT','PK',''],
				['total_gen_run_hr','REAL','','SUM(gens)'],['total_daily_used','REAL','','SUM(gens)'],
				['spare_tank_balance','REAL','','closing'],['blackout_hr','REAL','','MAX(gens)'],
				['days_of_buffer','REAL','','COMPUTED'],['num_generators_active','INT','','COUNT']
			]},
			{ name: 'fuel_purchases', color: '#ff9d00', cols: [
				['id','INT','PK',''],['sector_id','TEXT','FK','→ sectors'],
				['date','TEXT','',''],['supplier','TEXT','',''],
				['quantity_liters','REAL','',''],['price_per_liter','REAL','','MMK']
			]},
			{ name: 'daily_sales', color: '#9d4867', cols: [
				['id','INT','PK',''],['sales_site_name','TEXT','UK','= CostCenter'],
				['site_id','TEXT','FK','→ sites (auto-mapped)'],['sector_id','TEXT','',''],
				['date','TEXT','UK',''],['brand','TEXT','UK',''],
				['sales_amt','REAL','','MMK'],['margin','REAL','','MMK']
			]},
			{ name: 'hourly_sales', color: '#9d4867', cols: [
				['id','INT','PK',''],['sales_site_name','TEXT','UK','= CostCenter'],
				['site_id','TEXT','FK','→ sites (auto-mapped)'],['sector_id','TEXT','',''],
				['date','TEXT','UK',''],['hour','INT','UK','0-23'],
				['sales_amt','REAL','','MMK'],['trans_cnt','INT','','']
			]},
			{ name: 'store_master', color: '#ff9d00', cols: [
				['gold_code','TEXT','PK','POS ID'],['cost_center_code','TEXT','FK*','→ sites'],
				['cost_center_name','TEXT','','short code'],['segment_name','TEXT','',''],
				['latitude','REAL','','GPS'],['longitude','REAL','','GPS'],
				['address_state','TEXT','','region'],['address_township','TEXT','',''],
				['channel','TEXT','',''],['store_size','TEXT','','S/M/L/XL'],
				['sector_id','TEXT','FK','→ sectors']
			]},
			{ name: 'diesel_expense_ly', color: '#be2d06', cols: [
				['cost_center_code','TEXT','PK+FK*','→ sites'],
				['sector_id','TEXT','',''],['cost_center_name','TEXT','',''],
				['yearly_expense_mmk_mil','REAL','','MMK Mil'],['daily_avg_expense_mmk','REAL','','MMK'],
				['pct_on_sales','REAL','','ratio']
			]},
			{ name: 'alerts', color: '#be2d06', cols: [
				['id','INT','PK',''],['alert_type','TEXT','',''],['severity','TEXT','','CRIT/WARN/INFO'],
				['site_id','TEXT','FK','→ sites'],['message','TEXT','',''],['created_at','TEXT','','']
			]},
		]}
		<div class="space-y-6">
			<!-- CLI Header -->
			<div class="font-mono text-xs p-4" style="background: #1a1a1a; color: #00ff41; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
				<div>$ describe --schema bcp.db --format=erd</div>
				<div class="mt-1" style="color: #888;">// {erdTables.length} tables | SQLite WAL mode | cost_center_code = cross-file join key</div>
				<div class="mt-1" style="color: #ff9d00;">// FK* = cost_center_code link (sales ↔ sites ↔ store_master ↔ diesel_expense)</div>
			</div>

			<!-- Visual Join Diagram -->
			<div class="p-5 overflow-x-auto" style="background: #feffd6; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
				<div class="font-black uppercase text-sm mb-4" style="color: #383832;">DATA JOIN MAP — cost_center_code (7-digit)</div>

				<!-- Top row: 3 source boxes -->
				<div class="flex justify-center gap-4 mb-2">
					<div class="text-center px-4 py-2 text-[10px] font-black uppercase" style="background: #006f7c; color: white; border: 2px solid #383832; min-width: 160px;">
						<div>BLACKOUT FILES</div>
						<div class="font-normal text-[8px] mt-0.5 opacity-80">creates sites + generators</div>
					</div>
					<div class="text-center px-4 py-2 text-[10px] font-black uppercase" style="background: #9d4867; color: white; border: 2px solid #383832; min-width: 160px;">
						<div>CMHL_DAILY_SALES</div>
						<div class="font-normal text-[8px] mt-0.5 opacity-80">sales + store master + mapping</div>
					</div>
					<div class="text-center px-4 py-2 text-[10px] font-black uppercase" style="background: #be2d06; color: white; border: 2px solid #383832; min-width: 160px;">
						<div>DIESEL EXPENSE</div>
						<div class="font-normal text-[8px] mt-0.5 opacity-80">LY baseline cost</div>
					</div>
				</div>

				<!-- Arrows down -->
				<div class="flex justify-center gap-4 mb-2">
					<div class="text-center text-xs font-mono" style="color: #383832; min-width: 160px;">│ site_id</div>
					<div class="text-center text-xs font-mono" style="color: #383832; min-width: 160px;">│ cost_center_code</div>
					<div class="text-center text-xs font-mono" style="color: #383832; min-width: 160px;">│ cost_center_code</div>
				</div>
				<div class="flex justify-center gap-4 mb-2">
					<div class="text-center text-xs font-mono" style="color: #383832; min-width: 160px;">▼</div>
					<div class="text-center text-xs font-mono" style="color: #383832; min-width: 160px;">▼</div>
					<div class="text-center text-xs font-mono" style="color: #383832; min-width: 160px;">▼</div>
				</div>

				<!-- Middle row: 3 target boxes -->
				<div class="flex justify-center gap-4 mb-2">
					<div class="text-center px-4 py-3 text-[10px] font-black uppercase" style="background: #383832; color: #feffd6; border: 2px solid #383832; min-width: 160px;">
						<div class="text-sm">SITES</div>
						<div class="font-normal text-[8px] mt-1 opacity-80">PK: site_id</div>
						<div class="font-normal text-[8px] opacity-80">FK*: cost_center_code</div>
						<div class="font-normal text-[8px] mt-1" style="color: #00fc40;">+ lat/long, address, size</div>
					</div>
					<div class="text-center px-4 py-3 text-[10px] font-black uppercase" style="background: #ff9d00; color: #383832; border: 2px solid #383832; min-width: 160px;">
						<div class="text-sm">STORE MASTER</div>
						<div class="font-normal text-[8px] mt-1">gold_code, lat/long</div>
						<div class="font-normal text-[8px]">address, channel, size</div>
						<div class="font-normal text-[8px]">FK*: cost_center_code</div>
					</div>
					<div class="text-center px-4 py-3 text-[10px] font-black uppercase" style="background: #be2d06; color: white; border: 2px solid #383832; min-width: 160px;">
						<div class="text-sm">DIESEL EXPENSE</div>
						<div class="font-normal text-[8px] mt-1">yearly_cost, daily_avg</div>
						<div class="font-normal text-[8px]">pct_on_sales</div>
						<div class="font-normal text-[8px]">PK+FK*: cost_center_code</div>
					</div>
				</div>

				<!-- Arrow down from SITES -->
				<div class="flex justify-center mb-2">
					<div class="text-center text-xs font-mono" style="color: #383832; min-width: 160px;">│ site_id (FK)</div>
					<div style="min-width: 160px;"></div>
					<div style="min-width: 160px;"></div>
				</div>
				<div class="flex justify-center gap-4 mb-2">
					<div class="text-center text-xs font-mono" style="color: #383832; min-width: 160px;">├─────────────────────┐</div>
					<div style="min-width: 160px;"></div>
					<div style="min-width: 160px;"></div>
				</div>

				<!-- Bottom row: operations + sales -->
				<div class="flex justify-center gap-4">
					<div class="text-center px-4 py-2 text-[10px] font-black uppercase" style="background: #006f7c; color: white; border: 2px solid #383832; min-width: 160px;">
						<div>DAILY OPS</div>
						<div class="font-normal text-[8px] mt-0.5">daily_operations</div>
						<div class="font-normal text-[8px]">generators</div>
						<div class="font-normal text-[8px]">daily_site_summary</div>
					</div>
					<div class="text-center px-4 py-2 text-[10px] font-black uppercase" style="background: #9d4867; color: white; border: 2px solid #383832; min-width: 160px;">
						<div>SALES DATA</div>
						<div class="font-normal text-[8px] mt-0.5">daily_sales</div>
						<div class="font-normal text-[8px]">hourly_sales</div>
						<div class="font-normal text-[8px]">(via cost_center_code)</div>
					</div>
					<div class="text-center px-4 py-2 text-[10px] font-black uppercase" style="background: #ff9d00; color: #383832; border: 2px solid #383832; min-width: 160px;">
						<div>FUEL PRICES</div>
						<div class="font-normal text-[8px] mt-0.5">fuel_purchases</div>
						<div class="font-normal text-[8px]">(via sector_id)</div>
					</div>
				</div>

				<!-- Legend -->
				<div class="flex gap-4 mt-4 text-[9px] font-bold justify-center">
					<span class="px-2 py-0.5" style="background: #383832; color: #feffd6;">FK* = cost_center_code</span>
					<span class="px-2 py-0.5" style="background: #383832; color: #00fc40;">UNIVERSAL JOIN KEY</span>
					<span class="px-2 py-0.5" style="background: #ebe8dd; color: #383832;">7-digit numeric</span>
				</div>
			</div>

			<!-- Table Cards Grid -->
			<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
				{#each erdTables as tbl}
					<div style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832;">
						<div class="px-3 py-2 font-mono font-black uppercase text-sm flex justify-between items-center" style="background: {tbl.color}; color: {tbl.color === '#ff9d00' ? '#383832' : '#feffd6'};">
							<span>{tbl.name}</span>
							<span class="text-[10px] font-normal opacity-75">{tbl.cols.length} cols</span>
						</div>
						<div style="background: #1a1a1a;">
							{#each tbl.cols as [col, type, badge, ref]}
								<div class="flex px-3 py-1 text-[11px] font-mono items-center" style="border-bottom: 1px solid #2a2a2a;">
									<span class="flex-1" style="color: {badge.includes('FK') ? '#ff9d00' : badge.includes('PK') ? '#00ff41' : '#ccc'};">{col}</span>
									<span class="w-12 text-right" style="color: #555;">{type}</span>
									{#if badge}
										<span class="w-14 text-right font-black text-[9px]" style="color: {badge.includes('PK') ? '#00ff41' : badge.includes('FK') ? '#ff9d00' : '#006f7c'};">{badge}</span>
									{:else}
										<span class="w-14"></span>
									{/if}
									{#if ref}
										<span class="ml-2 text-[9px]" style="color: {ref === 'JOIN KEY' || ref === 'COMPUTED' ? '#ff9d00' : '#555'};">{ref}</span>
									{:else}
										<span class="ml-2 w-24"></span>
									{/if}
								</div>
							{/each}
						</div>
					</div>
				{/each}
			</div>

			<!-- Legend -->
			<div class="font-mono text-[11px] flex flex-wrap gap-6 p-3" style="background: #1a1a1a; color: #888; border: 2px solid #383832;">
				<span><span style="color: #00ff41;">PK</span> = Primary Key</span>
				<span><span style="color: #ff9d00;">FK</span> = Foreign Key</span>
				<span><span style="color: #ff9d00;">FK*</span> = cost_center_code join</span>
				<span><span style="color: #006f7c;">UK</span> = Unique Constraint</span>
				<span>TEXT | INT | REAL = types</span>
			</div>

			<!-- Computed Fields -->
			<div style="border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
				<div class="px-3 py-2 font-mono font-bold uppercase tracking-widest text-sm" style="background: #1a1a1a; color: #00ff41;">$ computed_fields --list</div>
				<div style="background: #1a1a1a;">
					{#each [
						{ field: 'days_of_buffer', formula: 'tank ÷ (7d_avg_blackout × rated_L/Hr)', tables: 'site_summary + generators' },
						{ field: 'energy_cost', formula: 'daily_used × price_per_liter', tables: 'daily_ops + fuel_purchases' },
						{ field: 'diesel_pct', formula: '(energy_cost ÷ sales_amt) × 100', tables: 'daily_ops + fuel + sales' },
						{ field: 'efficiency', formula: 'daily_used ÷ gen_run_hr', tables: 'daily_operations' },
						{ field: 'bcp_score', formula: 'fuel(35%) + coverage(30%) + power(20%) + resilience(15%)', tables: 'site_summary + generators' },
					] as f, i}
						<div class="flex px-4 py-2 text-[11px] font-mono" style="border-bottom: 1px solid #2a2a2a; {i % 2 ? 'background: #222;' : ''}">
							<span class="w-36 font-bold shrink-0" style="color: #00ff41;">{f.field}</span>
							<span class="flex-1" style="color: #ccc;">{f.formula}</span>
							<span class="text-right shrink-0" style="color: #555;">{f.tables}</span>
						</div>
					{/each}
				</div>
			</div>
		</div>

	{:else if activeTab === 'danger'}
		<div class="space-y-6">
			<div class="p-6" style="background: white; border: 3px solid #be2d06; box-shadow: 4px 4px 0px 0px #383832;">
				<div class="flex items-center gap-3 mb-4">
					<span class="material-symbols-outlined text-2xl" style="color: #be2d06;">warning</span>
					<div>
						<h2 class="text-2xl font-black uppercase" style="color: #be2d06;">DANGER_ZONE</h2>
						<p class="text-xs font-bold uppercase" style="color: #65655e;">IRREVERSIBLE_OPERATIONS — DATA_WILL_BE_PERMANENTLY_DELETED</p>
					</div>
				</div>

				<div class="space-y-3">
					<h3 class="text-sm font-black uppercase" style="color: #383832; border-bottom: 2px solid #383832; padding-bottom: 4px;">PURGE_BY_SECTOR</h3>
					<div class="grid grid-cols-2 md:grid-cols-4 gap-3">
						{#each [
							{ key: 'cmhl', label: 'CMHL', desc: 'City Mart Holdings — daily_operations + site_summary', icon: 'storefront' },
							{ key: 'cp', label: 'CP', desc: 'City Properties — daily_operations + site_summary', icon: 'apartment' },
							{ key: 'cfc', label: 'CFC', desc: 'City Food Concept — daily_operations + site_summary', icon: 'bakery_dining' },
							{ key: 'pg', label: 'PG', desc: 'PG Sector — daily_operations + site_summary', icon: 'local_shipping' },
						] as t}
							<button onclick={() => clearData(t.key)} class="p-4 text-left active:translate-x-[2px] active:translate-y-[2px]"
								style="background: white; border: 2px solid #be2d06; box-shadow: 3px 3px 0px 0px #be2d06;">
								<span class="material-symbols-outlined text-lg" style="color: #be2d06;">{t.icon}</span>
								<div class="text-sm font-black uppercase mt-1" style="color: #be2d06;">PURGE_{t.label}</div>
								<div class="text-[9px] font-bold mt-1" style="color: #65655e;">{t.desc}</div>
							</button>
						{/each}
					</div>

					<h3 class="text-sm font-black uppercase mt-6" style="color: #383832; border-bottom: 2px solid #383832; padding-bottom: 4px;">PURGE_BY_TYPE</h3>
					<div class="grid grid-cols-2 md:grid-cols-3 gap-3">
						{#each [
							{ key: 'fuel', label: 'FUEL_PRICES', desc: 'All fuel purchase records', icon: 'local_gas_station' },
							{ key: 'sales', label: 'SALES_DATA', desc: 'daily_sales + hourly_sales', icon: 'point_of_sale' },
						] as t}
							<button onclick={() => clearData(t.key)} class="p-4 text-left active:translate-x-[2px] active:translate-y-[2px]"
								style="background: white; border: 2px solid #be2d06; box-shadow: 3px 3px 0px 0px #be2d06;">
								<span class="material-symbols-outlined text-lg" style="color: #be2d06;">{t.icon}</span>
								<div class="text-sm font-black uppercase mt-1" style="color: #be2d06;">PURGE_{t.label}</div>
								<div class="text-[9px] font-bold mt-1" style="color: #65655e;">{t.desc}</div>
							</button>
						{/each}
					</div>

					<h3 class="text-sm font-black uppercase mt-6" style="color: #383832; border-bottom: 2px solid #383832; padding-bottom: 4px;">NUCLEAR_OPTION</h3>
					<button onclick={() => clearData('all')} class="w-full p-4 text-left active:translate-x-[2px] active:translate-y-[2px]"
						style="background: #383832; color: #feffd6; border: 2px solid #be2d06; box-shadow: 4px 4px 0px 0px #be2d06;">
						<div class="flex items-center gap-3">
							<span class="material-symbols-outlined text-2xl" style="color: #f95630;">delete_forever</span>
							<div>
								<div class="text-lg font-black uppercase">PURGE_ALL_DATA</div>
								<div class="text-[10px] font-bold opacity-70">Deletes ALL daily operations, site summaries, fuel prices, sales, alerts, and AI cache</div>
							</div>
						</div>
					</button>
				</div>
			</div>
		</div>
	{/if}
</div>
