<script lang="ts">
	import { page } from '$app/state';
	import { api } from '$lib/api';

	const nav = [
		{ icon: '🏠', label: 'Home', href: '/' },
		{ icon: '📊', label: 'Dashboard', href: '/dashboard' },
		{ icon: '💬', label: 'Chat', href: '/chat' },
		{ icon: '📤', label: 'Upload', href: '/upload' },
		{ icon: '⚙️', label: 'Settings', href: '/settings' }
	];

	function isActive(href: string) {
		return page.url.pathname === href || (href !== '/' && page.url.pathname.startsWith(href));
	}
</script>

<aside class="fixed left-0 top-0 h-full w-16 hover:w-48 bg-[#111827] border-r border-gray-800 transition-all duration-200 z-50 group overflow-hidden">
	<div class="p-3 border-b border-gray-800 text-center">
		<span class="text-2xl">🛡️</span>
		<span class="hidden group-hover:inline text-sm font-bold text-white ml-2">BCP</span>
	</div>

	<nav class="mt-4">
		{#each nav as item}
			<a href={item.href}
				class="flex items-center gap-3 px-4 py-3 text-sm transition
					{isActive(item.href) ? 'bg-blue-600/20 text-blue-400 border-r-2 border-blue-500' : 'text-gray-400 hover:text-white hover:bg-gray-800'}">
				<span class="text-lg">{item.icon}</span>
				<span class="hidden group-hover:inline whitespace-nowrap">{item.label}</span>
			</a>
		{/each}
	</nav>

	<div class="absolute bottom-4 left-0 w-full px-4">
		<button onclick={() => api.logout()}
			class="flex items-center gap-3 text-sm text-red-400 hover:text-red-300 cursor-pointer">
			<span class="text-lg">🚪</span>
			<span class="hidden group-hover:inline">Logout</span>
		</button>
	</div>
</aside>
