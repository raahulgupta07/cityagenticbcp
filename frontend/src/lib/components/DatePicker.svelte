<script lang="ts">
	let { from = $bindable(''), to = $bindable(''), label = 'DATE_RANGE' }: { from: string; to: string; label?: string } = $props();

	let open = $state(false);
	let viewDate = $state(new Date());
	let picking = $state<'from'|'to'>('from'); // which end user is picking

	const presets = [
		{ label: 'TODAY', days: 0 },
		{ label: 'YESTERDAY', days: 1 },
		{ label: '3D', days: 3 },
		{ label: '7D', days: 7 },
		{ label: '14D', days: 14 },
		{ label: '30D', days: 30 },
		{ label: '60D', days: 60 },
		{ label: 'ALL', days: -1 },
	];

	function toStr(d: Date) { return d.toISOString().slice(0, 10); }

	function applyPreset(days: number) {
		if (days === -1) { from = ''; to = ''; open = false; return; }
		const end = new Date();
		to = toStr(end);
		if (days === 0) { from = toStr(end); }
		else { const start = new Date(); start.setDate(start.getDate() - days); from = toStr(start); }
		open = false;
	}

	function prevMonth() { viewDate = new Date(viewDate.getFullYear(), viewDate.getMonth() - 1, 1); }
	function nextMonth() { viewDate = new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 1); }

	function calendarDays() {
		const year = viewDate.getFullYear();
		const month = viewDate.getMonth();
		const first = new Date(year, month, 1);
		const last = new Date(year, month + 1, 0);
		const startDay = (first.getDay() + 6) % 7;
		const days: (number | null)[] = [];
		for (let i = 0; i < startDay; i++) days.push(null);
		for (let d = 1; d <= last.getDate(); d++) days.push(d);
		return days;
	}

	function monthLabel() { return viewDate.toLocaleDateString('en-US', { month: 'long', year: 'numeric' }); }

	function dayStr(day: number) { return toStr(new Date(viewDate.getFullYear(), viewDate.getMonth(), day)); }

	function isFrom(day: number) { return from && dayStr(day) === from; }
	function isTo(day: number) { return to && dayStr(day) === to; }
	function isInRange(day: number) {
		if (!from || !to) return false;
		const d = dayStr(day);
		return d > from && d < to;
	}
	function isToday(day: number) { return dayStr(day) === toStr(new Date()); }

	function selectDay(day: number) {
		const d = dayStr(day);
		if (picking === 'from') {
			from = d;
			if (to && d > to) to = d;
			picking = 'to';
		} else {
			if (d < from) { from = d; picking = 'to'; }
			else { to = d; open = false; picking = 'from'; }
		}
	}

	function displayValue() {
		if (!from && !to) return label;
		const fmt = (v: string) => { const d = new Date(v + 'T00:00:00'); return d.toLocaleDateString('en-US', { day: 'numeric', month: 'short' }); };
		if (from && to) return `${fmt(from)} → ${fmt(to)}`;
		if (from) return `${fmt(from)} → ...`;
		return label;
	}
</script>

<div class="relative">
	<button onclick={() => { open = !open; picking = 'from'; }} class="flex items-center gap-2 px-3 py-2 text-xs font-bold uppercase w-full text-left" style="background: white; border: 2px solid #383832; color: {from ? '#383832' : '#828179'};">
		<span class="material-symbols-outlined text-sm" style="color: #383832;">date_range</span>
		{displayValue()}
	</button>

	{#if open}
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="fixed inset-0 z-40" onclick={() => open = false}></div>

		<div class="absolute top-full right-0 z-50 mt-1 flex" style="background: white; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832; width: 420px;">
			<!-- Left: Presets -->
			<div class="w-[100px] py-2" style="border-right: 1px solid #ebe8dd;">
				{#each presets as p}
					<button onclick={() => applyPreset(p.days)} class="w-full text-left px-3 py-1.5 text-[10px] font-black uppercase transition-colors hover:bg-[#f6f4e9]" style="color: #383832;">
						{p.label}
					</button>
				{/each}
				{#if from || to}
					<button onclick={() => { from = ''; to = ''; open = false; }} class="w-full text-left px-3 py-1.5 text-[10px] font-black uppercase" style="color: #be2d06; border-top: 1px solid #ebe8dd;">
						CLEAR
					</button>
				{/if}
			</div>

			<!-- Right: Calendar -->
			<div class="flex-1 p-4">
				<!-- Picking indicator -->
				<div class="flex gap-2 mb-3">
					<button onclick={() => picking = 'from'}
						class="flex-1 px-2 py-1.5 text-[10px] font-black uppercase text-center"
						style="border: 2px solid {picking === 'from' ? '#007518' : '#ebe8dd'}; background: {picking === 'from' ? '#007518' : 'white'}; color: {picking === 'from' ? 'white' : '#383832'};">
						FROM: {from || '—'}
					</button>
					<button onclick={() => picking = 'to'}
						class="flex-1 px-2 py-1.5 text-[10px] font-black uppercase text-center"
						style="border: 2px solid {picking === 'to' ? '#9d4867' : '#ebe8dd'}; background: {picking === 'to' ? '#9d4867' : 'white'}; color: {picking === 'to' ? 'white' : '#383832'};">
						TO: {to || '—'}
					</button>
				</div>

				<!-- Month Nav -->
				<div class="flex justify-between items-center mb-2">
					<button onclick={prevMonth} class="w-6 h-6 flex items-center justify-center font-bold text-sm" style="border: 1px solid #383832;">◀</button>
					<span class="text-xs font-black uppercase" style="color: #383832;">{monthLabel()}</span>
					<button onclick={nextMonth} class="w-6 h-6 flex items-center justify-center font-bold text-sm" style="border: 1px solid #383832;">▶</button>
				</div>

				<!-- Day Headers -->
				<div class="grid grid-cols-7 gap-0 text-center text-[10px] font-black uppercase mb-1" style="color: #828179;">
					<span>Mo</span><span>Tu</span><span>We</span><span>Th</span><span>Fr</span><span>Sa</span><span>Su</span>
				</div>

				<!-- Days Grid -->
				<div class="grid grid-cols-7 gap-0 text-center text-xs">
					{#each calendarDays() as day}
						{#if day === null}
							<span></span>
						{:else}
							<button
								onclick={() => selectDay(day)}
								class="w-8 h-8 flex items-center justify-center font-bold mx-auto"
								style="{isFrom(day)
									? 'background: #007518; color: white;'
									: isTo(day)
										? 'background: #9d4867; color: white;'
										: isInRange(day)
											? 'background: #e8f5e9; color: #007518;'
											: isToday(day)
												? 'background: #f6f4e9; color: #007518; border: 2px solid #007518;'
												: 'color: #383832;'}">
								{day}
							</button>
						{/if}
					{/each}
				</div>
			</div>
		</div>
	{/if}
</div>
