<script lang="ts">
	let { title, value, unit = '', subtitle = '', icon = 'timer', pct = 0, color = 'primary', variant = '' }: {
		title: string; value: string; unit?: string; subtitle?: string; icon?: string;
		pct?: number; color?: string; variant?: string;
	} = $props();

	const colorMap: Record<string, string> = {
		primary: '#007518',
		secondary: '#006f7c',
		tertiary: '#9d4867',
		error: '#be2d06',
	};

	const bgMap: Record<string, string> = {
		primary: 'white',
		secondary: 'white',
		tertiary: '#fe97b9',
		error: 'white',
	};
</script>

<div class="p-4 asymmetric-border stamp-shadow" style="background: {variant === 'accent' ? bgMap[color] || 'white' : 'white'}; border-color: #383832;">
	<div class="flex justify-between items-start mb-2">
		<span class="px-2 py-0.5 text-[10px] font-black uppercase" style="background: #383832; color: #feffd6;">{title}</span>
		<span class="material-symbols-outlined" style="color: {colorMap[color] || '#007518'};">{icon}</span>
	</div>
	<div class="text-4xl font-black tracking-tighter" style="color: #383832;">
		{value}<span class="text-lg">{unit}</span>
	</div>
	{#if pct > 0}
		<div class="mt-3 h-2 flex" style="background: #ebe8dd; border: 1px solid #383832;">
			<div class="h-full" style="background: {colorMap[color] || '#007518'}; width: {Math.min(pct, 100)}%;"></div>
		</div>
	{/if}
	{#if subtitle}
		<div class="mt-2 text-[10px] uppercase opacity-60 font-bold" style="color: #383832;">{subtitle}</div>
	{/if}
</div>

<style>
	.asymmetric-border {
		border-bottom-width: 4px;
		border-right-width: 4px;
		border-left-width: 2px;
		border-top-width: 2px;
		border-style: solid;
	}
	.stamp-shadow {
		box-shadow: 4px 4px 0px 0px rgba(56, 56, 50, 1);
	}
</style>
