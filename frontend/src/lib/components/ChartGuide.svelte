<script lang="ts">
	let { formula, sources, reading, explain }: {
		formula: string;
		sources: { data: string; file: string; col: string; method: string }[];
		reading: { color: string; text: string }[];
		explain: string;
	} = $props();

	let open = $state(false);

	const colors: Record<string, string> = {
		green: 'color: #007518', amber: 'color: #ff9d00', red: 'color: #be2d06',
		blue: 'color: #006f7c', orange: 'color: #ff9d00'
	};

	const badgeColors: Record<string, string> = {
		SUM: '#ff9d00', AVG: '#9d4867', LATEST: '#006f7c', COUNT: '#007518'
	};

	function getBadgeBg(method: string): string {
		for (const [key, color] of Object.entries(badgeColors)) {
			if (method.toUpperCase().includes(key)) return color;
		}
		return '#ff9d00';
	}
</script>

<details class="my-1" style="background: #f6f4e9; border: 1px solid #383832;" bind:open>
	<summary class="px-4 py-2 cursor-pointer text-xs font-bold uppercase flex items-center gap-2 select-none" style="color: #65655e;">
		<span style="color: #006f7c;">ℹ</span> CHART_GUIDE
		<span class="ml-auto text-[10px] transition-transform {open ? 'rotate-180' : ''}">▼</span>
	</summary>

	<div class="px-5 pb-4 text-[11px] leading-relaxed font-mono" style="color: #383832;">
		<div class="font-black text-xs mb-1 uppercase" style="color: #006f7c;">Formula</div>
		<div class="pl-3 mb-3" style="color: #383832;">{@html formula}</div>

		<div class="font-black text-xs mb-1 uppercase" style="color: #007518;">Data Source</div>
		<div class="pl-3 mb-3">
			<div class="grid grid-cols-[1fr_1fr_1fr_auto] gap-1 text-[10px] font-bold uppercase pb-1 mb-1" style="color: #65655e; border-bottom: 1px solid #383832;">
				<span>Data</span><span>File</span><span>Column</span><span>Method</span>
			</div>
			{#each sources as src}
				<div class="grid grid-cols-[1fr_1fr_1fr_auto] gap-1 py-1 items-center" style="border-bottom: 1px solid #ebe8dd;">
					<span style="color: #006f7c;">{src.data}</span>
					<span style="color: #007518;">{src.file}</span>
					<span style="color: #006f7c;">"{src.col}"</span>
					<span class="text-[10px] font-black px-1.5 py-0.5" style="background: {getBadgeBg(src.method)}; color: #feffd6;">{src.method}</span>
				</div>
			{/each}
		</div>

		<div class="font-black text-xs mb-1 uppercase" style="color: #ff9d00;">How to Read</div>
		<div class="pl-3 mb-3">
			{#each reading as r}
				<div class="py-0.5" style="{colors[r.color] || 'color: #383832'}">{r.text}</div>
			{/each}
		</div>

		<div class="font-black text-xs mb-1 uppercase" style="color: #9d4867;">Simple Explanation</div>
		<div class="pl-3" style="color: #383832;">{@html explain}</div>
	</div>
</details>
