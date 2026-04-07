<script lang="ts">
	import { onMount } from 'svelte';

	interface ToolCall { tool: string; preview: string }
	interface Message { role: 'user' | 'assistant'; content: string; tools?: ToolCall[] }

	let messages: Message[] = $state([]);
	let input = $state('');
	let loading = $state(false);
	let ws: WebSocket | null = $state(null);
	let connected = $state(false);
	let chatEnd: HTMLDivElement;
	let expandedTools: Set<number> = $state(new Set());

	const suggestions = [
		'Which sites have less than 3 days of fuel?',
		'Compare fuel efficiency across all sectors',
		'What will diesel prices be next week?',
		'Give me a BCP risk summary',
		'Which generators are underperforming?',
		'What are the top 5 most urgent sites?',
	];

	onMount(() => {
		const saved = localStorage.getItem('bcp_chat_history');
		if (saved) { try { messages = JSON.parse(saved); } catch {} }
		connect();
		return () => ws?.close();
	});

	function saveChat() {
		localStorage.setItem('bcp_chat_history', JSON.stringify(messages.slice(-50)));
	}

	function connect() {
		ws = new WebSocket('ws://localhost:8000/api/ws/chat');
		ws.onopen = () => { connected = true; };
		ws.onmessage = (e) => {
			const data = JSON.parse(e.data);
			if (data.type === 'message') {
				messages = [...messages, {
					role: 'assistant',
					content: data.content,
					tools: data.tools || [],
				}];
				saveChat();
			} else if (data.type === 'error') {
				messages = [...messages, {
					role: 'assistant',
					content: `Error: ${data.content}`,
				}];
				saveChat();
			}
			loading = false;
			setTimeout(() => chatEnd?.scrollIntoView({ behavior: 'smooth' }), 50);
		};
		ws.onclose = () => { connected = false; };
		ws.onerror = () => { connected = false; loading = false; };
	}

	function send(text?: string) {
		const msg = text || input.trim();
		if (!msg || !ws || ws.readyState !== WebSocket.OPEN) return;
		messages = [...messages, { role: 'user', content: msg }];
		saveChat();
		ws.send(msg);
		input = '';
		loading = true;
		setTimeout(() => chatEnd?.scrollIntoView({ behavior: 'smooth' }), 50);
	}

	function clearChat() {
		messages = [];
		localStorage.removeItem('bcp_chat_history');
		expandedTools = new Set();
		// Reconnect to reset server-side history
		ws?.close();
		setTimeout(connect, 300);
	}

	function toggleTools(idx: number) {
		const next = new Set(expandedTools);
		if (next.has(idx)) next.delete(idx); else next.add(idx);
		expandedTools = next;
	}

	function handleKey(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
	}
</script>

<div class="flex flex-col h-[calc(100vh-120px)]">
	<!-- Status bar -->
	<div class="flex items-center justify-between px-6 py-2" style="border-bottom: 2px solid #383832;">
		<div class="flex items-center gap-2">
			<div class="w-2 h-2" style="background: {connected ? '#007518' : '#be2d06'};"></div>
			<span class="text-[10px] font-bold uppercase tracking-wider" style="color: #383832;">{connected ? 'LINK_ACTIVE' : 'LINK_DOWN'}</span>
		</div>
		{#if messages.length > 0}
			<div class="flex items-center gap-2">
				<button onclick={clearChat} class="text-[10px] font-bold uppercase tracking-wider underline decoration-2 underline-offset-4 transition" style="color: #9d4867;">
					CLEAR_LOG
				</button>
				<button onclick={() => { messages = []; localStorage.removeItem('bcp_chat_history'); }}
					class="text-[10px] font-black uppercase px-3 py-1"
					style="background: #be2d06; color: white; border: 1px solid #383832;">
					CLEAR HISTORY
				</button>
			</div>
		{/if}
	</div>

	<!-- Messages -->
	<div class="flex-1 overflow-y-auto px-6 py-4 space-y-4 custom-scrollbar">
		{#if messages.length === 0}
			<div class="text-center mt-16">
				<div class="inline-block px-4 py-1 mb-4 font-bold uppercase tracking-widest text-xs" style="background: #383832; color: #feffd6;">BCP_CHAT_AGENT</div>
				<h2 class="text-3xl font-black uppercase tracking-tighter mb-2" style="color: #383832;">QUERY_TERMINAL</h2>
				<p class="text-sm font-bold uppercase tracking-wider opacity-50 mb-8" style="color: #383832;">Fuel, blackouts, costs, predictions, site status...</p>

				<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 max-w-3xl mx-auto">
					{#each suggestions as s}
						<button onclick={() => send(s)}
							class="text-left px-4 py-3 text-xs font-bold uppercase transition-all active:translate-x-[1px] active:translate-y-[1px]"
							style="background: #f6f4e9; border: 2px solid #383832; color: #383832;"
							onmouseenter={(e) => { (e.currentTarget as HTMLElement).style.background = '#ebe8dd'; }}
							onmouseleave={(e) => { (e.currentTarget as HTMLElement).style.background = '#f6f4e9'; }}>
							{s}
						</button>
					{/each}
				</div>
			</div>
		{/if}

		{#each messages as msg, idx}
			<div class="flex {msg.role === 'user' ? 'justify-end' : 'justify-start'} gap-3">
				{#if msg.role === 'assistant'}
					<div class="w-8 h-8 flex items-center justify-center text-sm flex-shrink-0" style="background: #383832; color: #feffd6;">SYS</div>
				{/if}

				<div class="max-w-[75%]">
					<div class="px-4 py-3 text-sm font-medium" style="{msg.role === 'user'
						? 'background: #007518; color: white; border: 2px solid #383832;'
						: 'background: #f6f4e9; color: #383832; border: 2px solid #383832;'}">
						<div class="whitespace-pre-wrap leading-relaxed">{msg.content}</div>
					</div>

					{#if msg.tools && msg.tools.length > 0}
						<button onclick={() => toggleTools(idx)}
							class="mt-1 text-[10px] font-bold uppercase tracking-wider flex items-center gap-1" style="color: #006f7c;">
							<span>TOOLS_USED: {msg.tools.length}</span>
							<span class="text-[8px]">{expandedTools.has(idx) ? '▲' : '▼'}</span>
						</button>

						{#if expandedTools.has(idx)}
							<div class="mt-1 p-3 space-y-2" style="background: #ebe8dd; border: 2px solid #383832;">
								{#each msg.tools as t}
									<div class="text-[10px]">
										<span class="font-black uppercase" style="color: #006f7c;">{t.tool}</span>
										{#if t.preview}
											<div class="font-mono opacity-60 mt-0.5 truncate" style="color: #383832;">{t.preview}</div>
										{/if}
									</div>
								{/each}
							</div>
						{/if}
					{/if}
				</div>

				{#if msg.role === 'user'}
					<div class="w-8 h-8 flex items-center justify-center text-sm flex-shrink-0" style="background: #9d4867; color: white;">USR</div>
				{/if}
			</div>
		{/each}

		{#if loading}
			<div class="flex justify-start gap-3">
				<div class="w-8 h-8 flex items-center justify-center text-sm flex-shrink-0" style="background: #383832; color: #feffd6;">SYS</div>
				<div class="px-4 py-3 text-sm font-bold uppercase tracking-wider" style="background: #f6f4e9; border: 2px solid #383832; color: #383832;">
					PROCESSING<span class="animate-pulse">...</span>
				</div>
			</div>
		{/if}

		<div bind:this={chatEnd}></div>
	</div>

	<!-- Input -->
	<div class="p-4" style="border-top: 2px solid #383832; background: #ebe8dd;">
		<div class="flex gap-3 max-w-4xl mx-auto">
			<textarea
				bind:value={input}
				onkeydown={handleKey}
				rows="1"
				placeholder={connected ? "ENTER_QUERY..." : "RECONNECTING..."}
				disabled={!connected}
				class="flex-1 px-4 py-3 text-sm font-bold resize-none focus:outline-none disabled:opacity-50"
				style="background: white; border: 2px solid #383832; color: #383832;"
			/>
			<button
				onclick={() => send()}
				disabled={loading || !input.trim() || !connected}
				class="px-6 font-black uppercase text-sm transition-all active:translate-x-[2px] active:translate-y-[2px] disabled:opacity-50"
				style="background: #00fc40; color: #383832; border: 2px solid #383832;"
			>
				SEND
			</button>
		</div>
	</div>
</div>
