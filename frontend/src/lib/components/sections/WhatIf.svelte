<script lang="ts">
	import { api } from '$lib/api';

	let consumptionChange = $state(0);
	let priceChange = $state(0);
	let targetDays = $state(7);
	let result: any = $state(null);
	let loading = $state(false);

	async function run() {
		loading = true;
		try {
			result = await api.get(`/whatif?consumption_change_pct=${consumptionChange}&price_change_pct=${priceChange}&target_days=${targetDays}`);
		} catch (e) { console.error(e); }
		loading = false;
	}

	function fmt(v: number) { return v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(1)+'K' : v.toFixed(0); }
</script>

<h2 class="text-lg font-black uppercase mt-6 mb-3" style="color: #383832;">🧪 What-If Simulator</h2>
<div class="p-5" style="background: white; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
	<div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
		<div>
			<label class="block text-[10px] uppercase mb-1" style="color: #65655e;">Fuel Consumption Change</label>
			<div class="flex items-center gap-2">
				<input type="range" bind:value={consumptionChange} min={-50} max={50} step={5} class="flex-1" />
				<span class="text-sm font-mono w-12 text-right" style="color: #383832;">{consumptionChange > 0 ? '+' : ''}{consumptionChange}%</span>
			</div>
		</div>
		<div>
			<label class="block text-[10px] uppercase mb-1" style="color: #65655e;">Fuel Price Change</label>
			<div class="flex items-center gap-2">
				<input type="range" bind:value={priceChange} min={-30} max={30} step={5} class="flex-1" />
				<span class="text-sm font-mono w-12 text-right" style="color: #383832;">{priceChange > 0 ? '+' : ''}{priceChange}%</span>
			</div>
		</div>
		<div>
			<label class="block text-[10px] uppercase mb-1" style="color: #65655e;">Target Buffer Days</label>
			<input type="number" bind:value={targetDays} min={1} max={30} class="w-full px-3 py-2 text-sm" style="background: #f6f4e9; border: 1px solid #383832; color: #383832;" />
		</div>
	</div>
	<button onclick={run} disabled={loading} class="w-full disabled:opacity-50 text-sm font-medium py-2.5 transition" style="background: #383832; color: #feffd6;">
		{loading ? 'Running...' : '▶ Run Simulation'}
	</button>

	{#if result}
		<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
			<div class="p-3 text-center" style="background: #f6f4e9; border: 1px solid #383832;">
				<div class="text-[10px] uppercase" style="color: #65655e;">Base Weekly Cost</div>
				<div class="text-lg font-bold" style="color: #383832;">{fmt(result.base_cost)}</div>
			</div>
			<div class="p-3 text-center" style="background: #f6f4e9; border: 1px solid #383832;">
				<div class="text-[10px] uppercase" style="color: #65655e;">New Weekly Cost</div>
				<div class="text-lg font-bold" style="color: {result.new_cost < result.base_cost ? '#007518' : '#be2d06'};">{fmt(result.new_cost)}</div>
			</div>
			<div class="p-3 text-center" style="background: #f6f4e9; border: 1px solid #383832;">
				<div class="text-[10px] uppercase" style="color: #65655e;">Savings / Extra</div>
				<div class="text-lg font-bold" style="color: {result.difference > 0 ? '#007518' : '#be2d06'};">{result.difference > 0 ? '+' : ''}{fmt(result.difference)}</div>
			</div>
			<div class="p-3 text-center" style="background: #f6f4e9; border: 1px solid #383832;">
				<div class="text-[10px] uppercase" style="color: #65655e;">Budget Change</div>
				<div class="text-lg font-bold" style="color: {result.pct_change < 0 ? '#007518' : '#be2d06'};">{result.pct_change > 0 ? '+' : ''}{result.pct_change}%</div>
			</div>
		</div>

		{#if result.buffer_projection}
			<div class="mt-3 p-3" style="background: {result.buffer_projection.feasible ? '#f0f9f0' : '#fef0f0'}; border: 1px solid {result.buffer_projection.feasible ? '#007518' : '#be2d06'};">
				<span class="text-sm font-bold" style="color: {result.buffer_projection.feasible ? '#007518' : '#be2d06'};">
					{result.buffer_projection.feasible ? '✅ FEASIBLE' : '❌ NOT FEASIBLE'}
				</span>
				<span class="text-xs ml-2" style="color: #65655e;">
					Avg buffer: {result.buffer_projection.avg_buffer} days | {result.buffer_projection.sites_below_target} sites below {targetDays}-day target
				</span>
			</div>
		{/if}
	{/if}
</div>
