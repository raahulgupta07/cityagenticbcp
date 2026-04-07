<script lang="ts">
	let { tabs, active = $bindable(''), onchange }: {
		tabs: string[]; active: string; onchange?: (tab: string) => void;
	} = $props();
</script>

<div class="flex gap-1 bg-[#111827] rounded-lg p-1 mb-4 overflow-x-auto">
	{#each tabs as tab}
		<button onclick={() => { active = tab; onchange?.(tab); }}
			class="px-4 py-2 text-sm font-medium rounded-md whitespace-nowrap transition
				{active === tab ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-700'}">
			{tab}
		</button>
	{/each}
</div>
