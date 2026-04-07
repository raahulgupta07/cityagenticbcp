<script lang="ts">
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import { onMount } from 'svelte';

	let { currentUser = null }: { currentUser?: any } = $props();

	let alertCount = $state(0);
	let searchQuery = $state('');
	let searchOpen = $state(false);

	onMount(async () => {
		try {
			const token = localStorage.getItem('token');
			if (!token) return;
			const res = await fetch('http://localhost:8000/api/alerts/active', {
				headers: { 'Authorization': `Bearer ${token}` }
			});
			if (res.ok) {
				const data = await res.json();
				alertCount = data.counts?.critical || 0;
			}
		} catch {}
	});

	const nav = [
		{ label: 'DASHBOARD', href: '/dashboard' },
		{ label: 'DICTIONARY', href: '/dashboard?view=dictionary' },
		{ label: 'BCP_CHAT', href: '/chat' },
		{ label: 'DATA_ENTRY', href: '/upload' },
		{ label: 'SETTINGS', href: '/settings' },
	];

	function isActive(href: string) {
		const path = page.url.pathname;
		if (href === '/dashboard') return path === '/dashboard' && !page.url.searchParams.has('view');
		if (href === '/dashboard?view=dictionary') return page.url.searchParams.get('view') === 'dictionary';
		return path.startsWith(href);
	}
</script>

<header class="fixed top-0 w-full z-50" style="border-bottom: 3px solid #383832; background: #feffd6;">
	<div class="flex justify-between items-center w-full px-6 py-3 max-w-[1920px] mx-auto">
		<div class="flex items-center gap-6">
			<span class="text-2xl font-bold tracking-tighter uppercase px-2 py-1" style="background: #383832; color: #feffd6;">BCP COMMAND CENTER</span>
			<nav class="hidden md:flex gap-1 text-sm font-bold uppercase tracking-tighter">
				{#each nav as item}
					<a href={item.href}
						class="px-2 py-1 transition-colors"
						style="{isActive(item.href) ? 'background: #383832; color: #feffd6;' : 'color: #383832;'}"
						onmouseenter={(e) => { if (!isActive(item.href)) { (e.target as HTMLElement).style.background = '#007518'; (e.target as HTMLElement).style.color = 'white'; }}}
						onmouseleave={(e) => { if (!isActive(item.href)) { (e.target as HTMLElement).style.background = 'transparent'; (e.target as HTMLElement).style.color = '#383832'; }}}>
						{item.label}
					</a>
				{/each}
			</nav>
		</div>
		<div class="flex items-center gap-4">
			<!-- Alert bell -->
			<div class="relative cursor-pointer" title="{alertCount} critical alerts">
				<span class="material-symbols-outlined text-lg" style="color: {alertCount > 0 ? '#be2d06' : '#383832'};">notifications</span>
				{#if alertCount > 0}
					<span class="absolute -top-1 -right-1 w-4 h-4 rounded-full text-[8px] font-black flex items-center justify-center"
						style="background: #be2d06; color: white;">{alertCount}</span>
				{/if}
			</div>
			<!-- Site Search -->
			<div class="relative">
				<button onclick={() => searchOpen = !searchOpen}
					class="flex items-center gap-1 px-2 py-1 text-[10px] font-bold uppercase"
					style="color: #383832;">
					<span class="material-symbols-outlined text-sm">search</span>
				</button>
				{#if searchOpen}
					<div class="absolute top-full right-0 mt-1 z-50" style="background: white; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832; width: 280px;">
						<input type="text" bind:value={searchQuery} placeholder="SEARCH SITE ID..."
							class="w-full px-3 py-2 text-xs font-mono uppercase"
							style="border: none; border-bottom: 1px solid #ebe8dd; color: #383832;"
							autofocus />
						<div class="max-h-[200px] overflow-y-auto text-xs">
							<p class="px-3 py-2 text-[10px]" style="color: #65655e;">Type a site ID then navigate to Dashboard > Site Dive</p>
						</div>
					</div>
				{/if}
			</div>
			<div class="text-right">
				<p class="text-sm font-bold uppercase tracking-tight" style="color: #383832;">{currentUser?.username?.toUpperCase() || 'USER'}</p>
				<button onclick={() => api.logout()} class="text-[10px] font-bold uppercase tracking-widest underline decoration-2 underline-offset-4" style="color: #9d4867;">LOGOUT</button>
			</div>
			<div class="w-10 h-10 flex items-center justify-center font-bold text-sm" style="background: #9d4867; color: white; border: 2px solid #383832;">{(currentUser?.username || 'U')[0].toUpperCase()}</div>
		</div>
	</div>
</header>
