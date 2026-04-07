<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';

	// ─── State ─────────────────────────────────────────────
	let currentUser: any = $state(null);
	let activeTab = $state('');
	let loading = $state(true);
	let message = $state('');
	let messageType = $state<'success' | 'error'>('success');

	// User Management
	let users: any[] = $state([]);
	let newUser = $state({ username: '', password: '', display_name: '', email: '', role: 'user', sectors: [] as string[] });
	let manageUserId = $state<number | null>(null);
	let changeRole = $state('user');
	let resetPass = $state('');

	// SMTP
	let smtp = $state({ server: '', port: 587, username: '', password: '', sender_name: 'CityBCPAgent', sender_email: '', use_tls: true, enabled: false, provider: 'Custom', is_configured: false });
	let testEmail = $state('');
	let smtpResult = $state('');
	let smtpTesting = $state(false);

	// Recipients
	let recipients: any[] = $state([]);
	let newRecipient = $state({ name: '', email: '', role: 'Manager', sectors: '', severity_filter: 'CRITICAL,WARNING' });

	// Email Log
	let emailLog: any = $state({ logs: [], sent_count: 0, failed_count: 0 });

	// Data Quality
	let dataQuality: any = $state({ spec_deviation: [], reporting_gaps: [], missing_specs: [] });

	// Scheduled Alerts
	let scheduleEnabled = $state(false);
	let scheduleTime = $state('08:00');
	let scheduleFreq = $state('daily');

	// Formula Engine
	let formulas: any = $state(null);
	let formulaSaving = $state(false);

	// System
	let systemStats: Record<string, number> = $state({});
	let confirmPurge = $state('');

	const SECTORS = ['CFC', 'CMHL', 'CP', 'PG'];
	const PRESETS: Record<string, { server: string; port: number; tls: boolean }> = {
		'Custom': { server: '', port: 587, tls: true },
		'Gmail': { server: 'smtp.gmail.com', port: 587, tls: true },
		'Outlook': { server: 'smtp-mail.outlook.com', port: 587, tls: true },
		'Office365': { server: 'smtp.office365.com', port: 587, tls: true },
		'Yahoo': { server: 'smtp.mail.yahoo.com', port: 587, tls: true },
		'SendGrid': { server: 'smtp.sendgrid.net', port: 587, tls: true },
		'Zoho': { server: 'smtp.zoho.com', port: 587, tls: true },
		'AmazonSES': { server: 'email-smtp.us-east-1.amazonaws.com', port: 587, tls: true },
	};
	const ROLES: Record<string, string> = { super_admin: 'ROOT_ADMIN', admin: 'OPERATOR', user: 'VIEWER' };

	onMount(async () => {
		try { currentUser = await api.get('/me'); } catch {}
		const isSA = currentUser?.role === 'super_admin';
		activeTab = isSA ? 'users' : 'recipients';
		await loadTabData(activeTab);
		loading = false;
	});

	function flash(msg: string, type: 'success'|'error' = 'success') {
		message = msg; messageType = type;
		setTimeout(() => message = '', 4000);
	}

	async function loadTabData(tab: string) {
		try {
			if (tab === 'users') users = await api.get('/users');
			else if (tab === 'smtp') smtp = await api.get('/smtp');
			else if (tab === 'recipients') recipients = await api.get('/recipients');
			else if (tab === 'email_log') emailLog = await api.get('/email-log');
			else if (tab === 'data_quality') dataQuality = await api.get('/data-quality');
			else if (tab === 'formulas') formulas = await api.get('/formulas');
			else if (tab === 'system') systemStats = await api.get('/system/stats');
		} catch (e: any) { if (e.message !== 'Unauthorized') flash(e.message, 'error'); }
	}

	async function switchTab(tab: string) { activeTab = tab; await loadTabData(tab); }

	// ─── User Actions ──────────────────────────────────────
	async function createUser() {
		if (!newUser.username || !newUser.password || !newUser.display_name) return flash('Username, password, and name required', 'error');
		if (newUser.password.length < 6) return flash('Min 6 chars', 'error');
		try {
			await api.post('/users', newUser);
			flash(`OPERATOR '${newUser.username}' PROVISIONED`);
			newUser = { username: '', password: '', display_name: '', email: '', role: 'user', sectors: [] };
			users = await api.get('/users');
		} catch (e: any) { flash(e.message, 'error'); }
	}
	async function toggleUser(id: number, active: number) { try { await api.put(`/users/${id}`, { is_active: active ? 0 : 1 }); users = await api.get('/users'); } catch (e: any) { flash(e.message, 'error'); } }
	async function updateRole(id: number) { try { await api.put(`/users/${id}`, { role: changeRole }); users = await api.get('/users'); flash('ROLE_UPDATED'); } catch (e: any) { flash(e.message, 'error'); } }
	async function resetPassword(id: number) { if (!resetPass || resetPass.length < 6) return flash('Min 6 chars', 'error'); try { await api.put(`/users/${id}`, { password: resetPass }); resetPass = ''; flash('PASSWORD_RESET'); } catch (e: any) { flash(e.message, 'error'); } }
	async function deleteUserById(id: number) { try { await api.delete(`/users/${id}`); users = await api.get('/users'); flash('OPERATOR_REMOVED'); } catch (e: any) { flash(e.message, 'error'); } }

	// ─── SMTP Actions ──────────────────────────────────────
	function applyPreset(provider: string) { const p = PRESETS[provider]; if (provider !== 'Custom') { smtp.server = p.server; smtp.port = p.port; smtp.use_tls = p.tls; } smtp.provider = provider; }
	async function saveSmtp() { try { await api.put('/smtp', smtp); flash('SMTP_CONFIG_SAVED'); smtp = await api.get('/smtp'); } catch (e: any) { flash(e.message, 'error'); } }
	async function sendTestEmail() {
		if (!testEmail) return flash('Enter address', 'error');
		smtpTesting = true;
		smtpResult = '';
		try {
			await api.post('/smtp/test', { to: testEmail });
			smtpResult = 'Email sent successfully';
			flash(`TEST_DISPATCHED -> ${testEmail}`);
		} catch (e: any) {
			smtpResult = (e.message || 'Failed to send test email');
		}
		smtpTesting = false;
	}

	// ─── Recipient Actions ─────────────────────────────────
	async function addRecipient() { if (!newRecipient.name || !newRecipient.email) return flash('Name + email required', 'error'); try { await api.post('/recipients', newRecipient); flash(`RECIPIENT_ADDED: ${newRecipient.name}`); newRecipient = { name: '', email: '', role: 'Manager', sectors: '', severity_filter: 'CRITICAL,WARNING' }; recipients = await api.get('/recipients'); } catch (e: any) { flash(e.message, 'error'); } }
	async function toggleRecipient(id: number) { try { await api.put(`/recipients/${id}`, {}); recipients = await api.get('/recipients'); } catch (e: any) { flash(e.message, 'error'); } }
	async function deleteRecipient(id: number) { try { await api.delete(`/recipients/${id}`); recipients = await api.get('/recipients'); flash('RECIPIENT_REMOVED'); } catch (e: any) { flash(e.message, 'error'); } }
	async function sendAlertsNow() { try { const res = await api.post('/alerts/send', {}); flash(res.sent > 0 ? `DISPATCHED_TO_${res.sent}_NODES` : res.message); } catch (e: any) { flash(e.message, 'error'); } }

	// ─── System Actions ────────────────────────────────────
	async function clearData(target: string) { try { await api.post(`/system/clear/${target}`, {}); flash(`PURGED: ${target.toUpperCase()}`); systemStats = await api.get('/system/stats'); } catch (e: any) { flash(e.message, 'error'); } }
	async function executePurge(target: string) { await clearData(target); }

	$effect(() => { if (manageUserId !== null) { const u = users.find((u: any) => u.id === manageUserId); if (u) changeRole = u.role; } });
	const isSuperAdmin = $derived(currentUser?.role === 'super_admin');
	const manageableUsers = $derived(users.filter((u: any) => u.username !== currentUser?.username));

	const superTabs = [
		{ id: 'users', label: 'USER_MGMT' },
		{ id: 'smtp', label: 'SMTP_CONFIG' },
		{ id: 'recipients', label: 'RECIPIENTS' },
		{ id: 'email_log', label: 'EMAIL_LOGS' },
		{ id: 'formulas', label: 'FORMULA_ENGINE' },
		{ id: 'data_quality', label: 'DATA_QUALITY' },
		{ id: 'system', label: 'SYS_RESOURCES' },
	];
	const adminTabs = [
		{ id: 'recipients', label: 'RECIPIENTS' },
		{ id: 'email_log', label: 'EMAIL_LOGS' },
		{ id: 'formulas', label: 'FORMULA_ENGINE' },
		{ id: 'data_quality', label: 'DATA_QUALITY' },
	];
	const tabs = $derived(isSuperAdmin ? superTabs : adminTabs);
</script>

{#if loading}
	<div class="flex items-center justify-center h-64 text-sm font-bold uppercase tracking-widest opacity-50">LOADING_CONFIG...</div>
{:else}

<!-- Flash message -->
{#if message}
	<div class="fixed top-20 right-6 z-50 px-4 py-3 text-sm font-bold uppercase tracking-wider" style="{messageType === 'success' ? 'background: #007518; color: white; border: 2px solid #383832;' : 'background: #be2d06; color: white; border: 2px solid #383832;'} box-shadow: 4px 4px 0px 0px #383832;">
		{message}
	</div>
{/if}

<div class="space-y-8">
	<!-- Page Header -->
	<div>
		<div class="inline-block px-4 py-1 mb-2 font-bold uppercase tracking-widest text-xs" style="background: #383832; color: #feffd6;">SYSTEM_CONFIG_DASHBOARD</div>
		<h1 class="text-5xl font-black uppercase tracking-tighter pb-2" style="border-bottom: 4px solid #383832;">SETTINGS_OVERRIDE</h1>
	</div>

	<!-- Tab Bar -->
	<div class="flex flex-wrap gap-2">
		{#each tabs as tab}
			<button onclick={() => switchTab(tab.id)}
				class="px-4 py-2 font-black text-sm uppercase transition-colors"
				style="{activeTab === tab.id ? 'background: #383832; color: #feffd6;' : 'background: transparent; color: #383832;'} border: 2px solid #383832;"
				onmouseenter={(e) => { if (activeTab !== tab.id) (e.target as HTMLElement).style.background = '#ebe8dd'; }}
				onmouseleave={(e) => { if (activeTab !== tab.id) (e.target as HTMLElement).style.background = 'transparent'; }}>
				{tab.label}
			</button>
		{/each}
	</div>

	<!-- ═══════════════════════════════════════════════════════ -->
	<!-- USER MANAGEMENT -->
	<!-- ═══════════════════════════════════════════════════════ -->
	{#if activeTab === 'users' && isSuperAdmin}
		<section class="grid grid-cols-1 lg:grid-cols-12 gap-8">
			<div class="lg:col-span-8 flex flex-col gap-8">
				<!-- Users Table -->
				<div class="p-6" style="background: #f6f4e9; border-bottom-width: 3px; border-right-width: 3px; border-left-width: 2px; border-top-width: 2px; border-style: solid; border-color: #383832; box-shadow: 4px 4px 0px 0px #383832;">
					<div class="flex items-center justify-between mb-6">
						<h2 class="text-xl font-black underline uppercase">USER_AUTHORITY_PROTOCOL</h2>
						<span class="px-2 font-bold text-xs text-white" style="background: #007518;">TOTAL: {String(users.length).padStart(2, '0')}_NODES</span>
					</div>
					{#if users.length > 0}
						<div class="overflow-x-auto" style="border: 2px solid #383832;">
							<table class="w-full text-left font-bold text-sm uppercase">
								<thead style="background: #383832; color: #feffd6;">
									<tr>
										<th class="p-3" style="border-right: 2px solid rgba(254,255,214,0.2);">OPERATOR_ID</th>
										<th class="p-3" style="border-right: 2px solid rgba(254,255,214,0.2);">DISPLAY</th>
										<th class="p-3" style="border-right: 2px solid rgba(254,255,214,0.2);">ACCESS_LVL</th>
										<th class="p-3" style="border-right: 2px solid rgba(254,255,214,0.2);">STATUS</th>
										<th class="p-3">LAST_PING</th>
									</tr>
								</thead>
								<tbody style="background: white;">
									{#each users as u, i}
										<tr style="border-bottom: 2px solid #383832; {i % 2 ? 'background: #ebe8dd;' : ''}" onmouseenter={(e) => (e.currentTarget as HTMLElement).style.background = '#f6f4e9'} onmouseleave={(e) => (e.currentTarget as HTMLElement).style.background = i % 2 ? '#ebe8dd' : 'white'}>
											<td class="p-3 font-mono" style="border-right: 2px solid #383832;">{u.username}</td>
											<td class="p-3" style="border-right: 2px solid #383832;">{u.display_name || '—'}</td>
											<td class="p-3" style="border-right: 2px solid #383832; color: {u.role === 'super_admin' ? '#006f7c' : '#007518'};">{ROLES[u.role] || u.role}</td>
											<td class="p-3" style="border-right: 2px solid #383832; color: {u.is_active ? '#007518' : '#be2d06'};">{u.is_active ? 'ONLINE' : 'REVOKED'}</td>
											<td class="p-3 text-xs opacity-60">{u.last_login?.slice(0, 16) || 'NEVER'}</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{/if}
				</div>

				<!-- Create User Form -->
				<div class="p-6" style="background: #ebe8dd; border-bottom-width: 3px; border-right-width: 3px; border-left-width: 2px; border-top-width: 2px; border-style: solid; border-color: #383832; box-shadow: 4px 4px 0px 0px #383832;">
					<h2 class="text-lg font-black underline uppercase mb-4">PROVISION_NEW_OPERATOR</h2>
					<div class="grid grid-cols-1 md:grid-cols-3 gap-3">
						{#each [
							{ label: 'OPERATOR_ID', bind: 'username', type: 'text', ph: 'john.doe' },
							{ label: 'DISPLAY_NAME', bind: 'display_name', type: 'text', ph: 'John Doe' },
							{ label: 'CONTACT_ADDR', bind: 'email', type: 'text', ph: 'john@hq.net' },
							{ label: 'PASSKEY', bind: 'password', type: 'password', ph: 'min 6 chars' },
						] as field}
							<div>
								<div class="inline-block px-2 py-0.5 text-[10px] font-black uppercase mb-1" style="background: #383832; color: #feffd6;">{field.label}</div>
								{#if field.bind === 'username'}
									<input bind:value={newUser.username} type={field.type} placeholder={field.ph} class="w-full px-3 py-2 text-sm font-bold" style="background: white; border: 2px solid #383832; font-family: 'Space Grotesk', sans-serif;" />
								{:else if field.bind === 'display_name'}
									<input bind:value={newUser.display_name} type={field.type} placeholder={field.ph} class="w-full px-3 py-2 text-sm font-bold" style="background: white; border: 2px solid #383832; font-family: 'Space Grotesk', sans-serif;" />
								{:else if field.bind === 'email'}
									<input bind:value={newUser.email} type={field.type} placeholder={field.ph} class="w-full px-3 py-2 text-sm font-bold" style="background: white; border: 2px solid #383832; font-family: 'Space Grotesk', sans-serif;" />
								{:else if field.bind === 'password'}
									<input bind:value={newUser.password} type={field.type} placeholder={field.ph} class="w-full px-3 py-2 text-sm font-bold" style="background: white; border: 2px solid #383832; font-family: 'Space Grotesk', sans-serif;" />
								{/if}
							</div>
						{/each}
						<div>
							<div class="inline-block px-2 py-0.5 text-[10px] font-black uppercase mb-1" style="background: #383832; color: #feffd6;">ACCESS_LEVEL</div>
							<select bind:value={newUser.role} class="w-full px-3 py-2 text-sm font-bold" style="background: white; border: 2px solid #383832; font-family: 'Space Grotesk', sans-serif;">
								<option value="admin">OPERATOR</option>
								<option value="user">VIEWER</option>
							</select>
						</div>
						<div>
							<div class="inline-block px-2 py-0.5 text-[10px] font-black uppercase mb-1" style="background: #383832; color: #feffd6;">SECTOR_ACCESS</div>
							<select bind:value={newUser.sectors} multiple class="w-full px-3 py-2 text-sm font-bold h-[38px]" style="background: white; border: 2px solid #383832; font-family: 'Space Grotesk', sans-serif;">
								{#each SECTORS as s}<option value={s}>{s}</option>{/each}
							</select>
						</div>
					</div>
					<button onclick={createUser} class="mt-4 w-full py-3 font-black uppercase transition-all active:translate-x-[2px] active:translate-y-[2px]" style="background: #00fc40; border: 2px solid #383832; color: #383832;">
						PROVISION_NEW_OPERATOR
					</button>
				</div>

				<!-- Manage Users -->
				{#if manageableUsers.length > 0}
					<div class="p-6" style="background: #f6f4e9; border-bottom-width: 3px; border-right-width: 3px; border-left-width: 2px; border-top-width: 2px; border-style: solid; border-color: #383832; box-shadow: 4px 4px 0px 0px #383832;">
						<h2 class="text-lg font-black underline uppercase mb-4">MANAGE_OPERATORS</h2>
						<select bind:value={manageUserId} class="w-full px-3 py-2 text-sm font-bold uppercase mb-4" style="background: white; border: 2px solid #383832; font-family: 'Space Grotesk', sans-serif;">
							<option value={null}>SELECT_OPERATOR...</option>
							{#each manageableUsers as u}
								<option value={u.id}>{u.username} — {ROLES[u.role] || u.role}</option>
							{/each}
						</select>

						{#if manageUserId !== null}
							{@const selectedUser = users.find((u: any) => u.id === manageUserId)}
							<div class="grid grid-cols-2 md:grid-cols-4 gap-3">
								<div class="p-3" style="border: 2px solid #383832; background: white;">
									<div class="text-[9px] font-black uppercase opacity-60 mb-2">TOGGLE_STATUS</div>
									<button onclick={() => toggleUser(manageUserId!, selectedUser?.is_active)} class="w-full py-2 text-xs font-black uppercase active:translate-x-[1px] active:translate-y-[1px]" style="border: 2px solid #383832; background: {selectedUser?.is_active ? '#be2d06' : '#007518'}; color: white;">
										{selectedUser?.is_active ? 'REVOKE' : 'ENABLE'}
									</button>
								</div>
								<div class="p-3" style="border: 2px solid #383832; background: white;">
									<div class="text-[9px] font-black uppercase opacity-60 mb-2">CHANGE_ROLE</div>
									<select bind:value={changeRole} class="w-full px-2 py-1 text-xs font-bold uppercase mb-2" style="border: 2px solid #383832; font-family: 'Space Grotesk', sans-serif;">
										<option value="admin">OPERATOR</option>
										<option value="user">VIEWER</option>
									</select>
									<button onclick={() => updateRole(manageUserId!)} class="w-full py-1 text-[10px] font-black uppercase active:translate-x-[1px] active:translate-y-[1px]" style="border: 2px solid #383832;">UPDATE</button>
								</div>
								<div class="p-3" style="border: 2px solid #383832; background: white;">
									<div class="text-[9px] font-black uppercase opacity-60 mb-2">RESET_PASSKEY</div>
									<input bind:value={resetPass} type="password" placeholder="new passkey" class="w-full px-2 py-1 text-xs font-bold mb-2" style="border: 2px solid #383832; font-family: 'Space Grotesk', sans-serif;" />
									<button onclick={() => resetPassword(manageUserId!)} class="w-full py-1 text-[10px] font-black uppercase active:translate-x-[1px] active:translate-y-[1px]" style="border: 2px solid #383832;">RESET</button>
								</div>
								<div class="p-3" style="border: 2px solid #383832; background: white;">
									<div class="text-[9px] font-black uppercase opacity-60 mb-2">DANGER_ZONE</div>
									<button onclick={() => deleteUserById(manageUserId!)} class="w-full py-2 text-xs font-black uppercase mt-4 active:translate-x-[1px] active:translate-y-[1px]" style="border: 2px solid #383832; background: #be2d06; color: white;">PURGE_OPERATOR</button>
								</div>
							</div>
						{/if}
					</div>
				{/if}
			</div>

			<!-- Sidebar: Current User -->
			<div class="lg:col-span-4 flex flex-col gap-8">
				{#if currentUser}
					<div class="p-6" style="background: #383832; color: #feffd6; border-bottom-width: 3px; border-right-width: 3px; border-left-width: 2px; border-top-width: 2px; border-style: solid; border-color: #383832; box-shadow: 4px 4px 0px 0px #383832;">
						<h2 class="text-sm font-black tracking-widest uppercase mb-4" style="border-bottom: 1px solid rgba(254,255,214,0.3); padding-bottom: 8px;">ACTIVE_SESSION</h2>
						<div class="space-y-3">
							<div>
								<div class="text-[10px] font-bold opacity-60">OPERATOR_ID</div>
								<div class="text-lg font-black">{currentUser.username?.toUpperCase()}</div>
							</div>
							<div>
								<div class="text-[10px] font-bold opacity-60">ACCESS_LEVEL</div>
								<div class="font-bold" style="color: #00fc40;">{ROLES[currentUser.role] || currentUser.role}</div>
							</div>
						</div>
					</div>
				{/if}
				<div class="p-6" style="background: #f6f4e9; border-bottom-width: 3px; border-right-width: 3px; border-left-width: 2px; border-top-width: 2px; border-style: solid; border-color: #383832; box-shadow: 4px 4px 0px 0px #383832;">
					<h2 class="text-sm font-black tracking-widest uppercase mb-4" style="border-bottom: 2px solid #383832; padding-bottom: 8px;">ROLE_MATRIX</h2>
					<div class="space-y-2 text-xs font-bold uppercase">
						<div class="flex justify-between pb-1" style="border-bottom: 1px solid rgba(56,56,50,0.2);"><span>ROOT_ADMIN</span><span style="color: #006f7c;">FULL_ACCESS</span></div>
						<div class="flex justify-between pb-1" style="border-bottom: 1px solid rgba(56,56,50,0.2);"><span>OPERATOR</span><span style="color: #007518;">UPLOAD+VIEW</span></div>
						<div class="flex justify-between"><span>VIEWER</span><span class="opacity-50">READ_ONLY</span></div>
					</div>
				</div>
			</div>
		</section>

	<!-- ═══════════════════════════════════════════════════════ -->
	<!-- SMTP CONFIG -->
	<!-- ═══════════════════════════════════════════════════════ -->
	{:else if activeTab === 'smtp' && isSuperAdmin}
		<section class="grid grid-cols-1 lg:grid-cols-12 gap-8">
			<div class="lg:col-span-8">
				<div class="p-6" style="background: #f6f4e9; border-bottom-width: 3px; border-right-width: 3px; border-left-width: 2px; border-top-width: 2px; border-style: solid; border-color: #383832; box-shadow: 4px 4px 0px 0px #383832;">
					<h2 class="text-xl font-black underline uppercase mb-2">SMTP_CONFIG_PROTOCOL</h2>
					<div class="mb-4">
						<div class="inline-block px-2 py-0.5 text-[10px] font-black uppercase mb-1" style="background: #383832; color: #feffd6;">PROVIDER_PRESET</div>
						<select onchange={(e) => applyPreset((e.target as HTMLSelectElement).value)} class="w-full px-3 py-2 text-sm font-bold uppercase" style="background: white; border: 2px solid #383832; font-family: 'Space Grotesk', sans-serif;">
							{#each Object.keys(PRESETS) as p}<option value={p} selected={smtp.provider === p}>{p.toUpperCase()}</option>{/each}
						</select>
					</div>
					<div class="grid grid-cols-1 md:grid-cols-3 gap-3">
						{#each [
							{ label: 'HOST', val: 'server' }, { label: 'PORT', val: 'port' }, { label: 'USERNAME', val: 'username' },
							{ label: 'PASSKEY', val: 'password' }, { label: 'SENDER_NAME', val: 'sender_name' }, { label: 'SENDER_ADDR', val: 'sender_email' },
						] as field}
							<div>
								<div class="inline-block px-2 py-0.5 text-[10px] font-black uppercase mb-1" style="background: #383832; color: #feffd6;">{field.label}</div>
								{#if field.val === 'server'}<input bind:value={smtp.server} class="w-full px-3 py-2 text-sm font-bold" style="background: white; border: 2px solid #383832; font-family: 'Space Grotesk', sans-serif;" />
								{:else if field.val === 'port'}<input bind:value={smtp.port} type="number" class="w-full px-3 py-2 text-sm font-bold" style="background: white; border: 2px solid #383832; font-family: 'Space Grotesk', sans-serif;" />
								{:else if field.val === 'username'}<input bind:value={smtp.username} class="w-full px-3 py-2 text-sm font-bold" style="background: white; border: 2px solid #383832; font-family: 'Space Grotesk', sans-serif;" />
								{:else if field.val === 'password'}<input bind:value={smtp.password} type="password" class="w-full px-3 py-2 text-sm font-bold" style="background: white; border: 2px solid #383832; font-family: 'Space Grotesk', sans-serif;" />
								{:else if field.val === 'sender_name'}<input bind:value={smtp.sender_name} class="w-full px-3 py-2 text-sm font-bold" style="background: white; border: 2px solid #383832; font-family: 'Space Grotesk', sans-serif;" />
								{:else if field.val === 'sender_email'}<input bind:value={smtp.sender_email} class="w-full px-3 py-2 text-sm font-bold" style="background: white; border: 2px solid #383832; font-family: 'Space Grotesk', sans-serif;" />
								{/if}
							</div>
						{/each}
					</div>
					<div class="flex gap-4 mt-4 text-sm font-bold uppercase">
						<label class="flex items-center gap-2 cursor-pointer"><input bind:checked={smtp.use_tls} type="checkbox" style="accent-color: #007518;" /> TLS_ENABLED</label>
						<label class="flex items-center gap-2 cursor-pointer"><input bind:checked={smtp.enabled} type="checkbox" style="accent-color: #007518;" /> ALERTS_ACTIVE</label>
					</div>
					<button onclick={saveSmtp} class="mt-4 w-full py-3 font-black uppercase transition-all active:translate-x-[2px] active:translate-y-[2px]" style="background: #00fc40; border: 2px solid #383832; color: #383832;">COMMIT_SMTP_CONFIG</button>
				</div>
			</div>
			<div class="lg:col-span-4 flex flex-col gap-8">
				<!-- Status -->
				<div class="p-6" style="background: {smtp.is_configured ? '#007518' : '#be2d06'}; color: white; border-bottom-width: 3px; border-right-width: 3px; border-left-width: 2px; border-top-width: 2px; border-style: solid; border-color: #383832; box-shadow: 4px 4px 0px 0px #383832;">
					<div class="text-[10px] font-black tracking-widest uppercase mb-2">CONNECTION_STATUS</div>
					<div class="text-2xl font-black">{smtp.is_configured ? 'ACTIVE' : 'OFFLINE'}</div>
					<div class="text-xs font-bold opacity-80 mt-1">{smtp.provider?.toUpperCase() || 'NO_PROVIDER'}</div>
				</div>
				<!-- Test -->
				<div class="p-6" style="background: #ebe8dd; border-bottom-width: 3px; border-right-width: 3px; border-left-width: 2px; border-top-width: 2px; border-style: solid; border-color: #383832; box-shadow: 4px 4px 0px 0px #383832;">
					<h2 class="text-sm font-black underline uppercase mb-3">TEST_DISPATCH</h2>
					<input bind:value={testEmail} placeholder="target@address.net" class="w-full px-3 py-2 text-sm font-bold mb-2" style="background: white; border: 2px solid #383832; font-family: 'Space Grotesk', sans-serif;" />
					<button onclick={sendTestEmail} disabled={smtpTesting} class="w-full py-2 text-[10px] font-black uppercase active:translate-x-[1px] active:translate-y-[1px] disabled:opacity-50" style="border: 2px solid #383832;">{smtpTesting ? 'SENDING...' : 'SEND_TEST_PACKET'}</button>
					{#if smtpResult}
						<div class="mt-2 text-xs font-mono px-3 py-1.5"
							style="background: {smtpResult.startsWith('Email sent') ? '#007518' : '#be2d06'}; color: white;">
							{smtpResult}
						</div>
					{/if}
				</div>
			</div>
		</section>

		<!-- Alert Schedule -->
		<div class="mt-6" style="border: 2px solid #383832;">
			<div class="px-4 py-2 font-black text-sm uppercase" style="background: #383832; color: #feffd6;">
				SCHEDULED ALERTS
			</div>
			<div class="p-4 space-y-3" style="background: white;">
				<label class="flex items-center gap-3 cursor-pointer">
					<input type="checkbox" bind:checked={scheduleEnabled} style="accent-color: #007518;" />
					<span class="text-xs font-bold uppercase" style="color: #383832;">Enable daily BCP summary email</span>
				</label>
				{#if scheduleEnabled}
					<div class="flex gap-4 items-end">
						<div>
							<label class="text-[9px] font-black uppercase" style="color: #65655e;">TIME</label>
							<input type="time" bind:value={scheduleTime}
								class="block px-3 py-1.5 text-xs font-mono"
								style="border: 2px solid #383832; color: #383832;" />
						</div>
						<div>
							<label class="text-[9px] font-black uppercase" style="color: #65655e;">FREQUENCY</label>
							<select bind:value={scheduleFreq}
								class="block px-3 py-1.5 text-xs font-bold uppercase"
								style="border: 2px solid #383832; color: #383832;">
								<option value="daily">DAILY</option>
								<option value="weekly">WEEKLY (MON)</option>
							</select>
						</div>
						<button class="px-4 py-1.5 text-[10px] font-black uppercase"
							style="background: #007518; color: white; border: 2px solid #383832;">
							SAVE SCHEDULE
						</button>
					</div>
					<p class="text-[10px]" style="color: #65655e;">
						Summary email includes: KPI snapshot, critical sites, buffer status, recommendations.
					</p>
				{/if}
			</div>
		</div>

	<!-- ═══════════════════════════════════════════════════════ -->
	<!-- RECIPIENTS -->
	<!-- ═══════════════════════════════════════════════════════ -->
	{:else if activeTab === 'recipients'}
		<div class="flex flex-col gap-8">
			{#if recipients.length > 0}
				<div class="p-6" style="background: #f6f4e9; border-bottom-width: 3px; border-right-width: 3px; border-left-width: 2px; border-top-width: 2px; border-style: solid; border-color: #383832; box-shadow: 4px 4px 0px 0px #383832;">
					<h2 class="text-xl font-black underline uppercase mb-4">RECIPIENT_REGISTRY</h2>
					<div class="overflow-x-auto" style="border: 2px solid #383832;">
						<table class="w-full text-left font-bold text-xs uppercase">
							<thead style="background: #383832; color: #feffd6;"><tr>
								<th class="p-3">NAME</th><th class="p-3">ADDRESS</th><th class="p-3">ROLE</th><th class="p-3">SECTORS</th><th class="p-3">FILTER</th><th class="p-3">STATUS</th><th class="p-3">CTRL</th>
							</tr></thead>
							<tbody style="background: white;">
								{#each recipients as r, i}
									<tr style="border-bottom: 2px solid #383832; {i % 2 ? 'background: #ebe8dd;' : ''}">
										<td class="p-3" style="border-right: 2px solid #383832;">{r.name}</td>
										<td class="p-3 font-mono" style="border-right: 2px solid #383832;">{r.email}</td>
										<td class="p-3" style="border-right: 2px solid #383832;">{r.role || '—'}</td>
										<td class="p-3" style="border-right: 2px solid #383832;">{r.sectors || 'ALL'}</td>
										<td class="p-3" style="border-right: 2px solid #383832;">{r.severity_filter || '—'}</td>
										<td class="p-3" style="border-right: 2px solid #383832; color: {r.is_active ? '#007518' : '#be2d06'};">{r.is_active ? 'ACTIVE' : 'DISABLED'}</td>
										<td class="p-3">
											<div class="flex gap-1">
												<button onclick={() => toggleRecipient(r.id)} class="px-2 py-1 text-[9px] font-black active:translate-x-[1px] active:translate-y-[1px]" style="border: 2px solid #383832;">TGL</button>
												<button onclick={() => deleteRecipient(r.id)} class="px-2 py-1 text-[9px] font-black active:translate-x-[1px] active:translate-y-[1px]" style="border: 2px solid #383832; background: #be2d06; color: white;">DEL</button>
											</div>
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</div>
			{/if}
			<!-- Add Recipient -->
			<div class="p-6" style="background: #ebe8dd; border-bottom-width: 3px; border-right-width: 3px; border-left-width: 2px; border-top-width: 2px; border-style: solid; border-color: #383832; box-shadow: 4px 4px 0px 0px #383832;">
				<h2 class="text-lg font-black underline uppercase mb-4">ADD_RECIPIENT_NODE</h2>
				<div class="grid grid-cols-1 md:grid-cols-3 gap-3">
					<div><div class="inline-block px-2 py-0.5 text-[10px] font-black uppercase mb-1" style="background: #383832; color: #feffd6;">NAME</div><input bind:value={newRecipient.name} placeholder="John Doe" class="w-full px-3 py-2 text-sm font-bold" style="background: white; border: 2px solid #383832; font-family: 'Space Grotesk', sans-serif;" /></div>
					<div><div class="inline-block px-2 py-0.5 text-[10px] font-black uppercase mb-1" style="background: #383832; color: #feffd6;">ADDRESS</div><input bind:value={newRecipient.email} placeholder="john@hq.net" class="w-full px-3 py-2 text-sm font-bold" style="background: white; border: 2px solid #383832; font-family: 'Space Grotesk', sans-serif;" /></div>
					<div><div class="inline-block px-2 py-0.5 text-[10px] font-black uppercase mb-1" style="background: #383832; color: #feffd6;">SECTORS</div><input bind:value={newRecipient.sectors} placeholder="CFC,CMHL" class="w-full px-3 py-2 text-sm font-bold" style="background: white; border: 2px solid #383832; font-family: 'Space Grotesk', sans-serif;" /></div>
				</div>
				<button onclick={addRecipient} class="mt-4 w-full py-3 font-black uppercase active:translate-x-[2px] active:translate-y-[2px]" style="background: #00fc40; border: 2px solid #383832; color: #383832;">REGISTER_RECIPIENT</button>
			</div>
			<button onclick={sendAlertsNow} class="w-full py-3 font-black uppercase active:translate-x-[2px] active:translate-y-[2px]" style="background: #be2d06; border: 2px solid #383832; color: white; box-shadow: 4px 4px 0px 0px #383832;">
				DISPATCH_CURRENT_ALERTS_NOW
			</button>
		</div>

	<!-- ═══════════════════════════════════════════════════════ -->
	<!-- EMAIL LOGS -->
	<!-- ═══════════════════════════════════════════════════════ -->
	{:else if activeTab === 'email_log'}
		<section class="grid grid-cols-1 lg:grid-cols-12 gap-8">
			<div class="lg:col-span-8">
				{#if emailLog.logs.length > 0}
					<div class="p-6" style="background: #f6f4e9; border-bottom-width: 3px; border-right-width: 3px; border-left-width: 2px; border-top-width: 2px; border-style: solid; border-color: #383832; box-shadow: 4px 4px 0px 0px #383832;">
						<h2 class="text-xl font-black underline uppercase mb-6 flex items-center gap-2">EMAIL_DISPATCH_LOG</h2>
						<div class="space-y-4 ml-2" style="border-left: 4px solid #383832;">
							{#each emailLog.logs.slice(0, 15) as log}
								<div class="relative pl-6 pb-4">
									<div class="absolute -left-[11px] top-0 w-4 h-4" style="background: {log.status === 'sent' ? '#007518' : '#be2d06'}; border: 2px solid #feffd6;"></div>
									<p class="text-[10px] font-black opacity-60">{log.sent_at?.slice(11, 19) || '—'}</p>
									<p class="font-bold text-[11px] uppercase leading-tight">{log.subject?.slice(0, 60) || 'UNNAMED'}</p>
									<div class="flex gap-2 mt-1">
										<span class="text-[9px] px-1 font-bold" style="background: {log.status === 'sent' ? '#007518' : '#be2d06'}; color: white;">{log.status?.toUpperCase()}</span>
										<span class="text-[9px] font-mono opacity-60">{log.recipient}</span>
									</div>
								</div>
							{/each}
						</div>
					</div>
				{:else}
					<div class="p-6 text-center font-bold uppercase opacity-50" style="background: #f6f4e9; border: 2px solid #383832;">NO_LOGS_RECORDED</div>
				{/if}
			</div>
			<div class="lg:col-span-4">
				<div class="p-6" style="background: #383832; color: #feffd6; border-bottom-width: 3px; border-right-width: 3px; border-left-width: 2px; border-top-width: 2px; border-style: solid; border-color: #383832; box-shadow: 4px 4px 0px 0px #383832;">
					<h2 class="text-sm font-black tracking-widest uppercase mb-4" style="border-bottom: 1px solid rgba(254,255,214,0.3); padding-bottom: 8px;">DISPATCH_METRICS</h2>
					<div class="space-y-4">
						<div><div class="flex justify-between text-[10px] font-bold mb-1"><span>DELIVERED</span><span style="color: #00fc40;">{emailLog.sent_count}</span></div><div class="h-2 w-full" style="background: rgba(254,255,214,0.1); border: 1px solid rgba(254,255,214,0.3);"><div class="h-full" style="background: #00fc40; width: {emailLog.sent_count + emailLog.failed_count > 0 ? emailLog.sent_count / (emailLog.sent_count + emailLog.failed_count) * 100 : 0}%;"></div></div></div>
						<div><div class="flex justify-between text-[10px] font-bold mb-1"><span>FAILED</span><span style="color: #f95630;">{emailLog.failed_count}</span></div><div class="h-2 w-full" style="background: rgba(254,255,214,0.1); border: 1px solid rgba(254,255,214,0.3);"><div class="h-full" style="background: #f95630; width: {emailLog.sent_count + emailLog.failed_count > 0 ? emailLog.failed_count / (emailLog.sent_count + emailLog.failed_count) * 100 : 0}%;"></div></div></div>
					</div>
				</div>
			</div>
		</section>

	<!-- ═══════════════════════════════════════════════════════ -->
	<!-- DATA QUALITY -->
	<!-- ═══════════════════════════════════════════════════════ -->
	{:else if activeTab === 'data_quality'}
		<div class="p-6" style="background: #383832; color: #feffd6; border-bottom-width: 3px; border-right-width: 3px; border-left-width: 2px; border-top-width: 2px; border-style: solid; border-color: #383832; box-shadow: 4px 4px 0px 0px #383832;">
			<h2 class="text-sm font-black tracking-widest uppercase mb-4" style="border-bottom: 1px solid rgba(254,255,214,0.3); padding-bottom: 8px;">DATA_QUALITY_INDEX</h2>
			<div class="space-y-4">
				<div>
					<div class="flex justify-between text-[10px] font-bold mb-1"><span>SPEC_DEVIATIONS</span><span style="color: {dataQuality.spec_deviation.length > 0 ? '#f95630' : '#00fc40'};">{dataQuality.spec_deviation.length} ANOMALIES</span></div>
					<div class="h-2 w-full" style="background: rgba(254,255,214,0.1); border: 1px solid rgba(254,255,214,0.3);"><div class="h-full" style="background: {dataQuality.spec_deviation.length > 0 ? '#f95630' : '#00fc40'}; width: {dataQuality.spec_deviation.length > 0 ? '60' : '100'}%;"></div></div>
				</div>
				<div>
					<div class="flex justify-between text-[10px] font-bold mb-1"><span>REPORTING_GAPS</span><span style="color: {dataQuality.reporting_gaps.length > 0 ? '#26e6ff' : '#00fc40'};">{dataQuality.reporting_gaps.length} SITES</span></div>
					<div class="h-2 w-full" style="background: rgba(254,255,214,0.1); border: 1px solid rgba(254,255,214,0.3);"><div class="h-full" style="background: {dataQuality.reporting_gaps.length > 0 ? '#26e6ff' : '#00fc40'}; width: {dataQuality.reporting_gaps.length > 0 ? '40' : '100'}%;"></div></div>
				</div>
				<div>
					<div class="flex justify-between text-[10px] font-bold mb-1"><span>MISSING_SPECS</span><span style="color: {dataQuality.missing_specs.length > 0 ? '#fe97b9' : '#00fc40'};">{dataQuality.missing_specs.length} GENERATORS</span></div>
					<div class="h-2 w-full" style="background: rgba(254,255,214,0.1); border: 1px solid rgba(254,255,214,0.3);"><div class="h-full" style="background: {dataQuality.missing_specs.length > 0 ? '#fe97b9' : '#00fc40'}; width: {dataQuality.missing_specs.length > 0 ? '30' : '100'}%;"></div></div>
				</div>
				<div class="p-3 text-[10px] font-mono leading-tight opacity-80" style="background: rgba(254,255,214,0.1);">
					&gt; RUN DQ_AUDIT_0xFF...<br/>
					&gt; SPEC_CHECK: {dataQuality.spec_deviation.length === 0 ? 'PASS' : `${dataQuality.spec_deviation.length} DEVIATIONS`}<br/>
					&gt; GAP_CHECK: {dataQuality.reporting_gaps.length === 0 ? 'PASS' : `${dataQuality.reporting_gaps.length} GAPS`}<br/>
					&gt; SPEC_MISSING: {dataQuality.missing_specs.length === 0 ? 'PASS' : `${dataQuality.missing_specs.length} NULL`}<br/>
					&gt; RESULT: {dataQuality.spec_deviation.length + dataQuality.reporting_gaps.length + dataQuality.missing_specs.length === 0 ? 'NOMINAL' : 'ATTENTION_REQUIRED'}
				</div>
			</div>
		</div>

		{#if dataQuality.spec_deviation.length > 0}
			<div class="p-6 mt-6" style="background: #f6f4e9; border-bottom-width: 3px; border-right-width: 3px; border-left-width: 2px; border-top-width: 2px; border-style: solid; border-color: #383832; box-shadow: 4px 4px 0px 0px #383832;">
				<h2 class="text-lg font-black underline uppercase mb-4">SPEC_DEVIATION_LOG</h2>
				<div class="overflow-x-auto" style="border: 2px solid #383832;">
					<table class="w-full text-left font-bold text-[10px] uppercase">
						<thead style="background: #383832; color: #feffd6;"><tr><th class="p-2">SITE</th><th class="p-2">SECTOR</th><th class="p-2">GEN</th><th class="p-2">RATED</th><th class="p-2">ACTUAL</th><th class="p-2">DEV%</th><th class="p-2">STATUS</th></tr></thead>
						<tbody style="background: white;">
							{#each dataQuality.spec_deviation as r, i}
								<tr style="border-bottom: 2px solid #383832; {i % 2 ? 'background: #ebe8dd;' : ''}">
									<td class="p-2" style="border-right: 2px solid #383832;">{r.site_id}</td>
									<td class="p-2" style="border-right: 2px solid #383832;">{r.sector_id}</td>
									<td class="p-2" style="border-right: 2px solid #383832;">{r.model_name}</td>
									<td class="p-2" style="border-right: 2px solid #383832;">{r.rated}</td>
									<td class="p-2" style="border-right: 2px solid #383832;">{r.actual_per_hr}</td>
									<td class="p-2 font-mono" style="border-right: 2px solid #383832; color: {Math.abs(r.deviation) > 50 ? '#be2d06' : '#006f7c'};">{r.deviation}%</td>
									<td class="p-2" style="color: {r.status === 'HIGH' ? '#be2d06' : '#006f7c'};">{r.status}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}

	<!-- ═══════════════════════════════════════════════════════ -->
	<!-- FORMULA ENGINE -->
	<!-- ═══════════════════════════════════════════════════════ -->
	{:else if activeTab === 'formulas' && formulas}
		{@const f = formulas}
		<div class="p-6" style="background: #f6f4e9; border: 2px solid #383832; box-shadow: 4px 4px 0px 0px #383832;">
			<div class="flex justify-between items-center mb-6">
				<div>
					<h2 class="text-xl font-black uppercase">FORMULA ENGINE</h2>
					<p class="text-[10px] mt-1" style="color: #65655e;">Configure how KPIs are calculated. Changes apply to all dashboards and tables.</p>
				</div>
				<div class="flex gap-2">
					<button onclick={async () => { formulaSaving = true; try { await api.put('/formulas', formulas); flash('Formulas saved'); } catch(e: any) { flash(e.message, 'error'); } formulaSaving = false; }}
						class="px-5 py-2 text-xs font-black uppercase" style="background: #007518; color: white; border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832;">
						{formulaSaving ? 'SAVING...' : 'SAVE & APPLY'}
					</button>
					<button onclick={async () => { try { await api.post('/formulas/reset', {}); formulas = await api.get('/formulas'); flash('Reset to defaults'); } catch(e: any) { flash(e.message, 'error'); } }}
						class="px-4 py-2 text-xs font-black uppercase" style="background: #ebe8dd; color: #383832; border: 2px solid #383832;">
						RESET
					</button>
				</div>
			</div>

			<!-- Global Settings -->
			<div class="mb-6 p-4" style="background: white; border: 2px solid #383832;">
				<div class="font-black uppercase text-sm mb-3" style="color: #383832;">GLOBAL SETTINGS</div>
				<div class="flex flex-wrap gap-6">
					<div>
						<label class="text-[9px] font-black uppercase block mb-1" style="color: #65655e;">LOOKBACK WINDOW (days)</label>
						<div class="flex gap-1">
							{#each [1, 3, 5, 7, 14, 30] as d}
								<button onclick={() => { f.lookback_days = d; formulas = {...f}; }}
									class="px-3 py-1.5 text-xs font-black"
									style="background: {f.lookback_days === d ? '#383832' : 'white'}; color: {f.lookback_days === d ? '#feffd6' : '#383832'}; border: 2px solid #383832;">
									{d}
								</button>
							{/each}
						</div>
						<p class="text-[8px] mt-1" style="color: #65655e;">Used for: Buffer, Blackout, Burn, Cost, Exp% averages</p>
					</div>
					<div>
						<label class="text-[9px] font-black uppercase block mb-1" style="color: #65655e;">ROLLING CHART WINDOW (days)</label>
						<div class="flex gap-1">
							{#each [3, 5, 7, 14] as d}
								<button onclick={() => { f.rolling_window = d; formulas = {...f}; }}
									class="px-3 py-1.5 text-xs font-black"
									style="background: {f.rolling_window === d ? '#383832' : 'white'}; color: {f.rolling_window === d ? '#feffd6' : '#383832'}; border: 2px solid #383832;">
									{d}
								</button>
							{/each}
						</div>
					</div>
					<div>
						<label class="text-[9px] font-black uppercase block mb-1" style="color: #65655e;">BUFFER TARGET (days for Diesel Needed)</label>
						<input type="number" bind:value={f.buffer_target_days} min="1" max="30"
							class="px-3 py-1.5 text-xs font-black w-16" style="border: 2px solid #383832; color: #383832;" />
					</div>
				</div>
			</div>

			<!-- KPI Formula Cards -->
			<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
				{#each [
					{ id: 'buffer', name: 'BUFFER DAYS', desc: 'How many days of fuel remaining', formula: `Last Day Tank ÷ AVG(Daily Burn) over ${f.lookback_days}d`, impacts: ['01 KPI Buffer', '03 Sector Sites', 'Site Modal', '02 Rolling Buffer'] },
					{ id: 'blackout', name: 'BLACKOUT HOURS', desc: 'Average power outage hours', formula: `AVG(Blackout Hr) over last ${f.lookback_days} days`, impacts: ['03 Sector Sites BO', '02 Trend Blackout', '02 Rolling Blackout'] },
					{ id: 'burn', name: 'DAILY BURN (L)', desc: 'Diesel consumed per day', formula: `AVG(Daily Used) over last ${f.lookback_days} days`, impacts: ['01 KPI Burn', '03 Sector Sites Burn', '06 Fuel Forecast'] },
					{ id: 'cost', name: 'DIESEL COST (MMK)', desc: 'Daily fuel expenditure', formula: `AVG(Daily Burn) × Latest Fuel Price`, impacts: ['01 KPI Cost', '03 Sector Sites Cost', '02 Trend Cost'] },
					{ id: 'exp_pct', name: 'EXPENSE % OF SALES', desc: 'Diesel as % of revenue', formula: `Diesel Cost ÷ AVG(Sales over ${f.lookback_days}d) × 100`, impacts: ['01 KPI Diesel%', '03 Sector Sites Exp%', '03 ACTION badge'] },
					{ id: 'efficiency', name: 'EFFICIENCY (L/Hr)', desc: 'Fuel per generator hour', formula: 'Total Used ÷ Total Gen Hours', impacts: ['02 Trend Efficiency', '02 Rolling Efficiency', 'Site Modal'] },
					{ id: 'needed', name: 'DIESEL NEEDED (L)', desc: 'How much to order', formula: `${f.buffer_target_days}d × AVG(Burn) − Tank`, impacts: ['01 KPI Needed', '04 Delivery Queue'] },
					{ id: 'variance', name: 'VARIANCE', desc: 'Actual vs expected consumption', formula: 'Actual Used − (Gen Hr × Rated L/Hr)', impacts: ['Site Modal Variance', '04 Waste/Theft Score'] },
				] as card}
					<div style="border: 2px solid #383832; box-shadow: 3px 3px 0px 0px #383832; background: white;">
						<div class="px-3 py-2 flex justify-between items-center" style="background: #383832; color: #feffd6;">
							<span class="font-black text-xs uppercase">{card.name}</span>
							<span class="text-[8px] opacity-60">{card.id}</span>
						</div>
						<div class="p-3">
							<p class="text-[10px] mb-2" style="color: #65655e;">{card.desc}</p>
							<div class="px-3 py-2 text-xs font-mono" style="background: #f6f4e9; border: 1px solid #ebe8dd; color: #006f7c;">
								= {card.formula}
							</div>
							<div class="mt-2">
								<span class="text-[8px] font-black uppercase" style="color: #65655e;">IMPACTS:</span>
								<div class="flex flex-wrap gap-1 mt-1">
									{#each card.impacts as imp}
										<span class="px-1.5 py-0.5 text-[7px] font-bold uppercase" style="background: #ebe8dd; color: #383832; border: 1px solid #383832;">{imp}</span>
									{/each}
								</div>
							</div>
						</div>
					</div>
				{/each}
			</div>

			<!-- Action Thresholds -->
			<div class="mb-6 p-4" style="background: white; border: 2px solid #383832;">
				<div class="font-black uppercase text-sm mb-3" style="color: #383832;">ACTION THRESHOLDS</div>
				<div class="grid grid-cols-1 md:grid-cols-2 gap-6">
					<!-- Buffer Status -->
					<div>
						<div class="text-[10px] font-black uppercase mb-2" style="color: #65655e;">BUFFER STATUS (days of fuel)</div>
						<div class="space-y-2">
							<div class="flex items-center gap-2">
								<span class="w-3 h-3 rounded-full" style="background: #be2d06;"></span>
								<span class="text-xs font-bold w-20">CRITICAL</span>
								<span class="text-[10px]">below</span>
								<input type="number" bind:value={f.thresholds.buffer_critical} min="1" max="30"
									class="px-2 py-1 text-xs font-black w-14 text-center" style="border: 2px solid #383832;" />
								<span class="text-[10px]">days</span>
							</div>
							<div class="flex items-center gap-2">
								<span class="w-3 h-3 rounded-full" style="background: #ff9d00;"></span>
								<span class="text-xs font-bold w-20">WARNING</span>
								<span class="text-[10px]">below</span>
								<input type="number" bind:value={f.thresholds.buffer_warning} min="1" max="30"
									class="px-2 py-1 text-xs font-black w-14 text-center" style="border: 2px solid #383832;" />
								<span class="text-[10px]">days</span>
							</div>
							<div class="flex items-center gap-2">
								<span class="w-3 h-3 rounded-full" style="background: #007518;"></span>
								<span class="text-xs font-bold w-20">SAFE</span>
								<span class="text-[10px]" style="color: #65655e;">above warning threshold</span>
							</div>
						</div>
					</div>
					<!-- Operating Mode -->
					<div>
						<div class="text-[10px] font-black uppercase mb-2" style="color: #65655e;">OPERATING MODE (diesel % of sales)</div>
						<div class="space-y-2">
							{#each [
								{ key: 'exp_open', label: 'OPEN', color: '#007518', prefix: 'below' },
								{ key: 'exp_monitor', label: 'MONITOR', color: '#ff9d00', prefix: 'below' },
								{ key: 'exp_reduce', label: 'REDUCE', color: '#f95630', prefix: 'below' },
								{ key: 'exp_close', label: 'CLOSE', color: '#be2d06', prefix: 'above' },
							] as t}
								<div class="flex items-center gap-2">
									<span class="w-3 h-3 rounded-full" style="background: {t.color};"></span>
									<span class="text-xs font-bold w-20">{t.label}</span>
									<span class="text-[10px]">{t.prefix}</span>
									<input type="number" bind:value={f.thresholds[t.key]} min="0" max="100" step="1"
										class="px-2 py-1 text-xs font-black w-14 text-center" style="border: 2px solid #383832;" />
									<span class="text-[10px]">%</span>
								</div>
							{/each}
						</div>
					</div>
				</div>
			</div>

			<!-- Heatmap Thresholds -->
			<div class="p-4" style="background: white; border: 2px solid #383832;">
				<div class="font-black uppercase text-sm mb-3" style="color: #383832;">HEATMAP ICON THRESHOLDS</div>
				<div class="overflow-x-auto">
					<table class="text-xs w-full">
						<thead>
							<tr style="background: #ebe8dd;">
								<th class="py-2 px-3 text-left font-black uppercase" style="border-bottom: 2px solid #383832;">METRIC</th>
								<th class="py-2 px-3 text-center font-black" style="border-bottom: 2px solid #383832; color: #007518;">🟢 GOOD</th>
								<th class="py-2 px-3 text-center font-black" style="border-bottom: 2px solid #383832; color: #ff9d00;">🟡 WATCH</th>
								<th class="py-2 px-3 text-center font-black" style="border-bottom: 2px solid #383832; color: #f95630;">🟠 WARN</th>
								<th class="py-2 px-3 text-center font-black" style="border-bottom: 2px solid #383832; color: #be2d06;">🔴 DANGER</th>
							</tr>
						</thead>
						<tbody>
							{#each [
								{ key: 'price', label: 'Price/L', unit: 'MMK', dir: '<' },
								{ key: 'blackout', label: 'Blackout Hr', unit: 'hr', dir: '<' },
								{ key: 'exp_pct', label: 'Expense %', unit: '%', dir: '<' },
								{ key: 'buffer', label: 'Buffer Days', unit: 'd', dir: '>' },
							] as row, ri}
								<tr style="background: {ri % 2 ? '#f6f4e9' : 'white'};">
									<td class="py-2 px-3 font-bold">{row.label}</td>
									{#each [0, 1, 2] as ci}
										<td class="py-2 px-3 text-center">
											<span class="text-[9px]">{row.dir}</span>
											<input type="number" bind:value={f.heatmap[row.key][ci]} step="0.1"
												class="px-1 py-0.5 text-xs font-black w-16 text-center" style="border: 1px solid #383832;" />
											<span class="text-[8px]">{row.unit}</span>
										</td>
									{/each}
									<td class="py-2 px-3 text-center text-[9px]" style="color: #65655e;">{row.dir === '<' ? '>' : '<'} {row.key === 'buffer' ? 'above' : 'below'}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		</div>

	<!-- SYSTEM -->
	<!-- ═══════════════════════════════════════════════════════ -->
	{:else if activeTab === 'system' && isSuperAdmin}
		<div class="p-6" style="background: #f6f4e9; border-bottom-width: 3px; border-right-width: 3px; border-left-width: 2px; border-top-width: 2px; border-style: solid; border-color: #383832; box-shadow: 4px 4px 0px 0px #383832;">
			<h2 class="text-xl font-black underline uppercase mb-6 flex items-center gap-2">SYSTEM_RESOURCE_ALLOCATION</h2>
			<div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
				{#each Object.entries(systemStats) as [table, count]}
					<div class="p-3 text-center" style="border: 2px solid #383832;">
						<p class="text-[9px] font-black uppercase opacity-60">{table.toUpperCase()}</p>
						<p class="text-2xl font-black">{typeof count === 'number' ? count.toLocaleString() : count}</p>
					</div>
				{/each}
			</div>
		</div>

		<div class="p-6 mt-6" style="background: #ebe8dd; border-bottom-width: 3px; border-right-width: 3px; border-left-width: 2px; border-top-width: 2px; border-style: solid; border-color: #be2d06; box-shadow: 4px 4px 0px 0px #383832;">
			<h2 class="text-lg font-black uppercase mb-4" style="color: #be2d06;">DANGER_ZONE — IRREVERSIBLE</h2>
			<div class="grid grid-cols-1 md:grid-cols-3 gap-3">
				{#each [
					{ key: 'ai_cache', label: 'PURGE_AI_CACHE' },
					{ key: 'alerts', label: 'PURGE_ALERTS' },
					{ key: 'email_log', label: 'PURGE_EMAIL_LOG' },
				] as btn}
					<button onclick={() => confirmPurge = btn.key} class="py-3 font-black text-xs uppercase active:translate-x-[2px] active:translate-y-[2px]" style="background: #be2d06; color: white; border: 2px solid #383832;">
						{btn.label}
					</button>
				{/each}
			</div>
		</div>
	{/if}

	{#if confirmPurge}
		<div class="fixed inset-0 z-[200] flex items-center justify-center" style="background: rgba(0,0,0,0.5);">
			<div class="p-6 max-w-sm" style="background: #feffd6; border: 3px solid #be2d06; box-shadow: 6px 6px 0px 0px #383832;">
				<div class="font-black uppercase text-sm mb-3" style="color: #be2d06;">CONFIRM PURGE</div>
				<p class="text-xs mb-4" style="color: #383832;">This will permanently delete all <b>{confirmPurge}</b> data. This cannot be undone.</p>
				<div class="flex gap-2">
					<button onclick={() => { executePurge(confirmPurge); confirmPurge = ''; }}
						class="flex-1 px-4 py-2 text-xs font-black uppercase"
						style="background: #be2d06; color: white; border: 2px solid #383832;">
						DELETE ALL
					</button>
					<button onclick={() => confirmPurge = ''}
						class="flex-1 px-4 py-2 text-xs font-black uppercase"
						style="background: #ebe8dd; color: #383832; border: 2px solid #383832;">
						CANCEL
					</button>
				</div>
			</div>
		</div>
	{/if}
</div>

{/if}
