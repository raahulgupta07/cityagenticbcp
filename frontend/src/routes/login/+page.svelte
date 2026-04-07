<script lang="ts">
	import { api } from '$lib/api';
	import { user, isAuthenticated } from '$lib/stores/auth';
	import { goto } from '$app/navigation';

	let username = $state('');
	let password = $state('');
	let error = $state('');
	let loading = $state(false);
	let showPassword = $state(false);

	async function handleLogin(e: Event) {
		e.preventDefault();
		error = '';
		loading = true;
		try {
			const u = await api.login(username, password);
			user.set(u);
			isAuthenticated.set(true);
			goto('/dashboard');
		} catch (e: any) {
			error = e.message || 'AUTHENTICATION_FAILED';
		} finally {
			loading = false;
		}
	}
</script>

<!-- Header -->
<header class="fixed top-0 w-full z-50" style="border-bottom: 3px solid #383832; background: #feffd6;">
	<div class="flex justify-between items-center px-6 py-3">
		<span class="text-2xl font-bold tracking-tighter uppercase px-2 py-1" style="background: #383832; color: #feffd6;">BCP COMMAND CENTER</span>
		<div class="flex gap-2 text-sm" style="color: #383832;">
			<span class="font-bold uppercase tracking-wider opacity-40">SECURE_TERMINAL</span>
		</div>
	</div>
</header>

<main class="min-h-screen flex items-center px-6 md:px-24" style="background: #feffd6;">
	<div class="w-full max-w-7xl mx-auto flex flex-col md:flex-row items-center md:items-start gap-16">

		<!-- Login Form -->
		<div class="w-full max-w-md pt-20">
			<div class="mb-10">
				<div class="inline-block px-4 py-1 mb-3 font-bold uppercase tracking-widest text-xs" style="background: #383832; color: #feffd6;">AUTHENTICATION_REQUIRED</div>
				<h1 class="text-5xl font-black uppercase tracking-tighter" style="color: #383832; border-bottom: 4px solid #383832; padding-bottom: 8px;">ACCESS_PORTAL</h1>
				<p class="text-sm font-bold uppercase tracking-wider mt-3 opacity-50" style="color: #383832;">City Holdings Myanmar — BCP Operations</p>
			</div>

			<form onsubmit={handleLogin} class="p-8 ink-border stamp-shadow" style="background: #f6f4e9;">

				{#if error}
					<div class="p-3 mb-6 font-bold text-sm uppercase" style="background: #be2d06; color: white; border: 2px solid #383832;">
						{error}
					</div>
				{/if}

				<div class="space-y-5">
					<div>
						<div class="inline-block px-2 py-0.5 text-[10px] font-black uppercase mb-1" style="background: #383832; color: #feffd6;">OPERATOR_ID</div>
						<input type="text" bind:value={username} placeholder="Enter credentials" class="w-full px-4 py-3 text-sm font-bold" style="background: white; border: 2px solid #383832;" />
					</div>

					<div>
						<div class="inline-block px-2 py-0.5 text-[10px] font-black uppercase mb-1" style="background: #383832; color: #feffd6;">ACCESS_KEY</div>
						<div class="relative">
							<input type={showPassword ? 'text' : 'password'} bind:value={password} placeholder="••••••••" class="w-full px-4 py-3 pr-12 text-sm font-bold" style="background: white; border: 2px solid #383832;" />
							<button type="button" onclick={() => showPassword = !showPassword}
								class="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-black uppercase tracking-wider"
								style="color: #828179;" title={showPassword ? 'Hide' : 'Show'}>
								{showPassword ? 'HIDE' : 'SHOW'}
							</button>
						</div>
					</div>

					<button type="submit" disabled={loading}
						class="w-full py-4 font-black uppercase tracking-wider text-sm transition-all active:translate-x-[2px] active:translate-y-[2px] disabled:opacity-50"
						style="background: #00fc40; color: #383832; border: 2px solid #383832;">
						{loading ? 'AUTHENTICATING...' : 'INITIATE_AUTHENTICATION'}
					</button>
				</div>
			</form>

			<div class="mt-6 flex items-center gap-4 text-[10px] uppercase tracking-widest font-bold opacity-40" style="color: #383832;">
				<div class="flex items-center gap-2">
					<span class="w-2 h-2" style="background: #007518;"></span>
					NODE_ACTIVE
				</div>
				<span>|</span>
				<div>AES-256</div>
				<span>|</span>
				<div>v2.0-STABLE</div>
			</div>

			<p class="mt-4 text-[10px] font-bold uppercase tracking-wider opacity-30" style="color: #383832;">DEFAULT: admin / admin123</p>
		</div>

		<!-- Right side decoration -->
		<div class="hidden lg:flex flex-1 justify-end items-center pt-20">
			<div class="text-right space-y-4">
				<h2 class="text-8xl font-black uppercase tracking-tighter leading-none select-none opacity-5" style="color: #383832;">
					CITY<br/>HOLDINGS<br/>MYANMAR
				</h2>
				<div class="flex justify-end gap-8 text-2xl font-black tracking-widest uppercase opacity-5" style="color: #383832;">
					<span>60+ SITES</span>
					<span>REAL-TIME</span>
				</div>
			</div>
		</div>
	</div>
</main>

<footer class="fixed bottom-0 w-full px-6 py-4 flex justify-between" style="background: #feffd6;">
	<span class="text-[10px] tracking-widest uppercase font-bold opacity-20" style="color: #383832;">© 2026 City Holdings Myanmar</span>
	<span class="text-[10px] tracking-widest uppercase font-bold opacity-20" style="color: #383832;">SECURE_TERMINAL</span>
</footer>
