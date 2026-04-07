<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	onMount(() => { goto(api.isLoggedIn() ? '/dashboard' : '/login'); });
</script>
<div class="min-h-screen flex items-center justify-center bg-[#0a0a0a] text-gray-500">Redirecting...</div>
