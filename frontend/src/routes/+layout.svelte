<script lang="ts">
	import '../app.css';
	let { children } = $props();

	let toasts: { id: number; message: string; type: string }[] = $state([]);
	let toastId = 0;

	// Expose globally
	if (typeof window !== 'undefined') {
		(window as any).__toast = (message: string, type: string = 'info') => {
			const id = ++toastId;
			toasts = [...toasts, { id, message, type }];
			setTimeout(() => { toasts = toasts.filter(t => t.id !== id); }, 4000);
		};
	}
</script>

<svelte:head>
	<title>BCP Command Center</title>
</svelte:head>

{@render children()}

<!-- Toast notifications -->
{#if toasts.length > 0}
	<div class="fixed bottom-20 right-4 z-[300] flex flex-col gap-2">
		{#each toasts as t (t.id)}
			<div class="px-4 py-2.5 text-xs font-bold uppercase flex items-center gap-2 animate-slide-in"
				style="background: {t.type === 'error' ? '#be2d06' : t.type === 'success' ? '#007518' : '#383832'}; color: #feffd6; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832; min-width: 250px;">
				<span class="material-symbols-outlined text-sm">{t.type === 'error' ? 'error' : t.type === 'success' ? 'check_circle' : 'info'}</span>
				{t.message}
			</div>
		{/each}
	</div>
{/if}
