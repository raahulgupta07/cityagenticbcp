<script lang="ts">
	let { data, columns, title = '' }: {
		data: Record<string, any>[];
		columns: { key: string; label: string }[];
		title?: string;
	} = $props();

	let search = $state('');
	let sortKey = $state('');
	let sortAsc = $state(true);

	function sorted() {
		let rows = data.filter(r =>
			search === '' || Object.values(r).some(v => String(v).toLowerCase().includes(search.toLowerCase()))
		);
		if (sortKey) {
			rows = [...rows].sort((a, b) => {
				const va = a[sortKey], vb = b[sortKey];
				const cmp = typeof va === 'number' ? va - vb : String(va).localeCompare(String(vb));
				return sortAsc ? cmp : -cmp;
			});
		}
		return rows;
	}

	function toggleSort(key: string) {
		if (sortKey === key) { sortAsc = !sortAsc; }
		else { sortKey = key; sortAsc = true; }
	}
</script>

<div class="bg-[#111827] rounded-xl border border-gray-800 overflow-hidden">
	{#if title}
		<div class="bg-[#0f172a] px-4 py-2.5 font-bold text-sm text-white">{title}</div>
	{/if}
	<div class="px-4 py-2">
		<input type="text" bind:value={search} placeholder="Search..."
			class="w-full bg-[#0a0a0a] border border-gray-700 rounded px-3 py-1.5 text-xs text-white" />
	</div>
	<div class="overflow-x-auto">
		<table class="w-full text-xs">
			<thead>
				<tr class="bg-[#1e293b] text-gray-400">
					{#each columns as col}
						<th class="px-3 py-2 text-left cursor-pointer hover:text-white" onclick={() => toggleSort(col.key)}>
							{col.label} {sortKey === col.key ? (sortAsc ? '▲' : '▼') : ''}
						</th>
					{/each}
				</tr>
			</thead>
			<tbody>
				{#each sorted() as row, i}
					<tr class="{i % 2 === 0 ? 'bg-[#111827]' : 'bg-[#0f172a]'} hover:bg-gray-800">
						{#each columns as col}
							<td class="px-3 py-2 text-gray-300">{row[col.key] ?? '—'}</td>
						{/each}
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</div>
