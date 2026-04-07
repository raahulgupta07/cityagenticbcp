const BASE = 'http://localhost:8000/api';

function getToken(): string | null {
	if (typeof window === 'undefined') return null;
	return localStorage.getItem('token');
}

async function request(method: string, path: string, body?: unknown) {
	const token = getToken();
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (token) headers['Authorization'] = `Bearer ${token}`;

	const res = await fetch(`${BASE}${path}`, {
		method,
		headers,
		body: body ? JSON.stringify(body) : undefined
	});

	if (res.status === 401) {
		localStorage.removeItem('token');
		if (typeof window !== 'undefined') window.location.href = '/login';
		throw new Error('Unauthorized');
	}

	if (!res.ok) {
		const err = await res.json().catch(() => ({ detail: res.statusText }));
		throw new Error(err.detail || res.statusText);
	}

	return res.json();
}

export const api = {
	get: (path: string) => request('GET', path),
	post: (path: string, body: unknown) => request('POST', path, body),
	put: (path: string, body: unknown) => request('PUT', path, body),
	delete: (path: string) => request('DELETE', path),

	async login(username: string, password: string) {
		const data = await request('POST', '/login', { username, password });
		localStorage.setItem('token', data.access_token);
		return data.user;
	},

	logout() {
		localStorage.removeItem('token');
		if (typeof window !== 'undefined') window.location.href = '/login';
	},

	isLoggedIn(): boolean {
		return !!getToken();
	}
};

export async function downloadExcel(
	data: any[],
	tableName: string,
	opts: { columns?: string[]; filters?: string; statusColumns?: string[] } = {}
) {
	if (!data.length) return;
	const token = getToken();
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (token) headers['Authorization'] = `Bearer ${token}`;

	const res = await fetch(`${BASE}/export/excel`, {
		method: 'POST',
		headers,
		body: JSON.stringify({
			table_name: tableName,
			data,
			columns: opts.columns || null,
			filters: opts.filters || null,
			status_columns: opts.statusColumns || null,
		}),
	});

	if (!res.ok) return;
	const blob = await res.blob();
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = `${tableName.replace(/\s+/g, '_')}_${new Date().toISOString().slice(0, 10)}.xlsx`;
	a.click();
	URL.revokeObjectURL(url);
}
