<script lang="ts">
	let {
		sector = $bindable('All Sectors'),
		company = $bindable('All Companies'),
		siteId = $bindable('All Sites'),
		dateFrom = $bindable(''),
		dateTo = $bindable(''),
		sectors = [], companies = [], sites = [],
		onrun
	}: {
		sector: string; company: string; siteId: string;
		dateFrom: string; dateTo: string;
		sectors: string[]; companies: string[]; sites: string[];
		onrun?: () => void;
	} = $props();

	let open = $state(false);
	let activeLabel = $state('ALL DATA');
	let viewDate = $state(new Date());

	const presets = [
		{ label: 'Today', days: 0 },
		{ label: 'Yesterday', days: 1 },
		{ label: '3 Days', days: 3 },
		{ label: '7 Days', days: 7 },
		{ label: '14 Days', days: 14 },
		{ label: '30 Days', days: 30 },
		{ label: '60 Days', days: 60 },
	];

	function setPreset(label: string, days: number) {
		const to = new Date();
		const from = new Date();
		if (days === 0) { dateFrom = toStr(to); dateTo = toStr(to); }
		else { from.setDate(to.getDate() - days + 1); dateFrom = toStr(from); dateTo = toStr(to); }
		activeLabel = label;
		open = false;
		onrun?.();
	}

	function setAll() { dateFrom = ''; dateTo = ''; activeLabel = 'ALL DATA'; open = false; onrun?.(); }
	function toStr(d: Date) { return d.toISOString().slice(0, 10); }
	function prevMonth() { viewDate = new Date(viewDate.getFullYear(), viewDate.getMonth() - 1, 1); }
	function nextMonth() { viewDate = new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 1); }

	function calendarDays() {
		const year = viewDate.getFullYear(); const month = viewDate.getMonth();
		const first = new Date(year, month, 1); const last = new Date(year, month + 1, 0);
		const startDay = (first.getDay() + 6) % 7;
		const days: (number | null)[] = [];
		for (let i = 0; i < startDay; i++) days.push(null);
		for (let d = 1; d <= last.getDate(); d++) days.push(d);
		return days;
	}

	function monthLabel() { return viewDate.toLocaleDateString('en-US', { month: 'long', year: 'numeric' }); }

	function selectDay(day: number) {
		const d = new Date(viewDate.getFullYear(), viewDate.getMonth(), day);
		const s = toStr(d);
		if (!dateFrom || (dateFrom && dateTo && dateFrom !== dateTo)) {
			dateFrom = s; dateTo = ''; activeLabel = s;
		} else {
			if (s < dateFrom) { dateTo = dateFrom; dateFrom = s; } else { dateTo = s; }
			activeLabel = `${dateFrom} → ${dateTo}`;
			open = false; onrun?.();
		}
	}

	function isInRange(day: number) {
		if (!day || !dateFrom) return false;
		const s = toStr(new Date(viewDate.getFullYear(), viewDate.getMonth(), day));
		if (!dateTo) return s === dateFrom;
		return s >= dateFrom && s <= dateTo;
	}
	function isStart(day: number) { if (!day || !dateFrom) return false; return toStr(new Date(viewDate.getFullYear(), viewDate.getMonth(), day)) === dateFrom; }
	function isEnd(day: number) { if (!day || !dateTo) return false; return toStr(new Date(viewDate.getFullYear(), viewDate.getMonth(), day)) === dateTo; }

	function displayRange() {
		if (!dateFrom && !dateTo) return 'ALL DATA';
		if (dateFrom && !dateTo) return dateFrom;
		if (dateFrom === dateTo) return dateFrom;
		return `${dateFrom} → ${dateTo}`;
	}
</script>

<!-- Date Range Only (tabs handle sector/company/site) -->
<div class="flex items-center gap-4 mb-6">
	<div class="relative flex-1 max-w-md">
		<div class="inline-block px-2 py-0.5 text-[9px] font-black uppercase mb-1" style="background: #383832; color: #feffd6;">DATE_RANGE</div>
		<button onclick={() => open = !open}
			class="w-full flex items-center gap-2 px-3 py-2 text-sm font-bold uppercase text-left active:translate-x-[1px] active:translate-y-[1px]"
			style="background: white; border: 2px solid #383832; color: #383832;">
			<span class="material-symbols-outlined text-sm" style="color: #007518;">calendar_today</span>
			<span class="flex-1 truncate">{displayRange()}</span>
			<span class="text-[8px]">{open ? '▲' : '▼'}</span>
		</button>

		{#if open}
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div class="fixed inset-0 z-40" onclick={() => open = false}></div>
			<div class="absolute top-full left-0 z-50 mt-1 flex" style="background: white; border: 3px solid #383832; box-shadow: 4px 4px 0px 0px #383832; width: 480px;">
				<!-- Presets -->
				<div class="w-[170px] py-2" style="border-right: 2px solid #ebe8dd;">
					{#each presets as p}
						<button onclick={() => setPreset(p.label, p.days)}
							class="w-full text-left px-4 py-2.5 text-xs font-bold uppercase flex justify-between transition-colors"
							style="color: #383832; {activeLabel === p.label ? 'background: #f6f4e9;' : ''}"
							onmouseenter={(e) => (e.currentTarget as HTMLElement).style.background = '#f6f4e9'}
							onmouseleave={(e) => (e.currentTarget as HTMLElement).style.background = activeLabel === p.label ? '#f6f4e9' : 'transparent'}>
							<span>{p.label}</span>
							<span style="color: #828179;">{p.days === 0 ? '' : p.days + 'd'}</span>
						</button>
					{/each}
					<div style="border-top: 1px solid #ebe8dd;">
						<button onclick={setAll} class="w-full text-left px-4 py-2.5 text-xs font-bold uppercase" style="color: #007518;">All Data</button>
					</div>
				</div>
				<!-- Calendar -->
				<div class="flex-1 p-4">
					<div class="flex justify-between items-center mb-3">
						<span class="text-sm font-bold" style="color: #383832;">{monthLabel()}</span>
						<div class="flex items-center gap-1">
							<button onclick={() => { viewDate = new Date(); }} class="text-[10px] font-bold uppercase px-2 py-1" style="color: #007518;">Today</button>
							<button onclick={prevMonth} class="w-6 h-6 flex items-center justify-center font-bold" style="border: 1px solid #383832;">&#8593;</button>
							<button onclick={nextMonth} class="w-6 h-6 flex items-center justify-center font-bold" style="border: 1px solid #383832;">&#8595;</button>
						</div>
					</div>
					<div class="grid grid-cols-7 gap-0 text-center text-[10px] font-bold uppercase mb-1" style="color: #828179;">
						<span>Mo</span><span>Tu</span><span>We</span><span>Th</span><span>Fr</span><span>Sa</span><span>Su</span>
					</div>
					<div class="grid grid-cols-7 gap-0 text-center text-xs">
						{#each calendarDays() as day}
							{#if day === null}
								<span class="w-8 h-8"></span>
							{:else}
								<button onclick={() => selectDay(day)}
									class="w-8 h-8 flex items-center justify-center font-bold mx-auto transition-colors"
									style="{isStart(day) || isEnd(day) ? 'background: #007518; color: white;' : isInRange(day) ? 'background: rgba(0,117,24,0.15); color: #007518;' : 'color: #383832;'}">
									{day}
								</button>
							{/if}
						{/each}
					</div>
					{#if dateFrom && !dateTo}
						<p class="text-[10px] font-bold uppercase mt-3" style="color: #9d4867;">SELECT_END_DATE...</p>
					{/if}
				</div>
			</div>
		{/if}
	</div>
</div>
