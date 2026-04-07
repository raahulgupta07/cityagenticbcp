import { writable } from 'svelte/store';

interface User {
	id: number;
	username: string;
	role: string;
	display_name?: string;
	email?: string;
}

export const user = writable<User | null>(null);
export const isAuthenticated = writable(false);
