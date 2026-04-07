// Chart option builders — each returns an ECharts option object

function fmt(v: number): string {
	if (Math.abs(v) >= 1e9) return (v / 1e9).toFixed(1) + 'B';
	if (Math.abs(v) >= 1e6) return (v / 1e6).toFixed(1) + 'M';
	if (Math.abs(v) >= 1e3) return (v / 1e3).toFixed(1) + 'K';
	return v.toLocaleString();
}

export function barChart(categories: string[], values: number[], opts: { title?: string; color?: string } = {}) {
	return {
		title: { text: opts.title || '', left: 'center', textStyle: { fontSize: 14 } },
		tooltip: { trigger: 'axis' },
		xAxis: { type: 'category', data: categories, axisLabel: { rotate: categories.length > 10 ? 45 : 0, fontSize: 10 } },
		yAxis: { type: 'value', axisLabel: { formatter: (v: number) => fmt(v) } },
		series: [{ type: 'bar', data: values, itemStyle: { color: opts.color || '#3b82f6' }, label: { show: categories.length <= 12, position: 'top', formatter: (p: any) => fmt(p.value), fontSize: 10 } }],
		grid: { top: 50, bottom: 40, left: 60, right: 20 }
	};
}

export function lineChart(categories: string[], series: { name: string; data: number[]; color: string }[], opts: { title?: string; markLines?: { value: number; label: string; color: string }[] } = {}) {
	const s = series.map(s => ({
		type: 'line' as const, name: s.name, data: s.data, lineStyle: { color: s.color },
		itemStyle: { color: s.color }, symbol: 'circle', symbolSize: 4,
		label: { show: series.length <= 2 && categories.length <= 12, position: 'top', formatter: (p: any) => fmt(p.value), fontSize: 9 },
		markLine: undefined as any
	}));
	if (opts.markLines && s.length > 0) {
		s[0].markLine = { silent: true, data: opts.markLines.map(m => ({ yAxis: m.value, label: { formatter: m.label, fontSize: 10 }, lineStyle: { color: m.color, type: 'dashed' } })) };
	}
	return {
		title: { text: opts.title || '', left: 'center', textStyle: { fontSize: 14 } },
		tooltip: { trigger: 'axis' },
		legend: { bottom: 0, textStyle: { fontSize: 10 } },
		xAxis: { type: 'category', data: categories, axisLabel: { rotate: categories.length > 10 ? 45 : 0, fontSize: 10 } },
		yAxis: { type: 'value', axisLabel: { formatter: (v: number) => fmt(v) } },
		series: s,
		grid: { top: 50, bottom: 40, left: 60, right: 20 }
	};
}

export function dualAxisChart(categories: string[], barData: number[], lineData: number[], opts: { title?: string; barName?: string; lineName?: string; barColor?: string; lineColor?: string } = {}) {
	return {
		title: { text: opts.title || '', left: 'center', textStyle: { fontSize: 14 } },
		tooltip: { trigger: 'axis' },
		legend: { bottom: 0, textStyle: { fontSize: 10 } },
		xAxis: { type: 'category', data: categories, axisLabel: { rotate: categories.length > 10 ? 45 : 0, fontSize: 10 } },
		yAxis: [
			{ type: 'value', name: opts.barName || 'Bar', axisLabel: { formatter: (v: number) => fmt(v) } },
			{ type: 'value', name: opts.lineName || 'Line', axisLabel: { formatter: (v: number) => fmt(v) } }
		],
		series: [
			{ type: 'bar', name: opts.barName || 'Bar', data: barData, yAxisIndex: 0, itemStyle: { color: opts.barColor || '#3b82f6' }, label: { show: categories.length <= 12, position: 'top', formatter: (p: any) => fmt(p.value), fontSize: 9 } },
			{ type: 'line', name: opts.lineName || 'Line', data: lineData, yAxisIndex: 1, itemStyle: { color: opts.lineColor || '#ef4444' }, lineStyle: { color: opts.lineColor || '#ef4444' }, symbol: 'circle', symbolSize: 4 }
		],
		grid: { top: 60, bottom: 40, left: 70, right: 70 }
	};
}

export function hbarChart(categories: string[], values: number[], opts: { title?: string; colors?: string[] } = {}) {
	return {
		title: { text: opts.title || '', left: 'center', textStyle: { fontSize: 14 } },
		tooltip: { trigger: 'axis' },
		xAxis: { type: 'value', axisLabel: { formatter: (v: number) => fmt(v) } },
		yAxis: { type: 'category', data: categories, axisLabel: { fontSize: 10 }, inverse: true },
		series: [{ type: 'bar', data: values.map((v, i) => ({ value: v, itemStyle: opts.colors ? { color: opts.colors[i] } : {} })), label: { show: true, position: 'right', formatter: (p: any) => fmt(p.value), fontSize: 10 } }],
		grid: { top: 40, bottom: 20, left: 120, right: 60 }
	};
}

export function groupedBar(categories: string[], series: { name: string; data: number[]; color: string }[], opts: { title?: string } = {}) {
	return {
		title: { text: opts.title || '', left: 'center', textStyle: { fontSize: 14 } },
		tooltip: { trigger: 'axis' },
		legend: { bottom: 0, textStyle: { fontSize: 10 } },
		xAxis: { type: 'category', data: categories, axisLabel: { fontSize: 10 } },
		yAxis: { type: 'value', axisLabel: { formatter: (v: number) => fmt(v) } },
		series: series.map(s => ({ type: 'bar' as const, name: s.name, data: s.data, itemStyle: { color: s.color } })),
		grid: { top: 50, bottom: 40, left: 60, right: 20 }
	};
}

export function pieChart(data: { name: string; value: number }[], opts: { title?: string } = {}) {
	return {
		title: { text: opts.title || '', left: 'center', textStyle: { fontSize: 14 } },
		tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
		series: [{ type: 'pie', radius: ['40%', '70%'], data, label: { formatter: '{b}\n{d}%', fontSize: 10 } }]
	};
}

export function radarChart(indicators: { name: string; max: number }[], series: { name: string; data: number[]; color: string }[], opts: { title?: string } = {}) {
	return {
		title: { text: opts.title || '', left: 'center', textStyle: { fontSize: 14 } },
		legend: { bottom: 0, textStyle: { fontSize: 10 } },
		radar: { indicator: indicators, shape: 'polygon' },
		series: [{ type: 'radar', data: series.map(s => ({ value: s.data, name: s.name, lineStyle: { color: s.color }, areaStyle: { color: s.color, opacity: 0.15 }, itemStyle: { color: s.color } })) }]
	};
}
