<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import AppHeader from '$lib/components/AppHeader.svelte';
	import FooterBar from '$lib/components/FooterBar.svelte';

	let { children } = $props();
	let ready = $state(false);
	let currentUser: any = $state(null);

	onMount(async () => {
		if (!api.isLoggedIn()) { goto('/login'); return; }
		try { currentUser = await api.get('/me'); } catch(e) { goto('/login'); return; }
		ready = true;
	});
</script>

{#if ready}
<AppHeader {currentUser} />
<main class="pt-16 pb-16 px-6 max-w-[1920px] mx-auto min-h-screen" style="background: #feffd6; color: #383832;">
	{@render children()}
</main>
<FooterBar />
{:else}
	<div class="min-h-screen flex items-center justify-center font-bold uppercase tracking-widest text-sm" style="background: #feffd6; color: #383832;">LOADING...</div>
{/if}
