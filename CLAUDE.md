# CLAUDE.md — Project Guide for AI Assistants

## What is this project?

CityBCPAgent is a Business Continuity Planning dashboard for managing backup generators and fuel supply across 60+ sites in Myanmar. It helps decision-makers during power outages and diesel shortages. It compares energy (fuel) costs against sales revenue to recommend whether stores should stay open. The app has two architectures: a legacy **Streamlit** monolith and a new **FastAPI + SvelteKit** v2 frontend with hierarchical drill-down: Group > Sector (Business Sector) > Company > Site.

## Tech Stack
- **Frontend (v2):** SvelteKit + ECharts (MiniChart.svelte sparklines), served via Vite
- **Frontend (legacy):** Streamlit 1.50 + streamlit-shadcn-ui 0.1.19 + ECharts (via streamlit-echarts)
- **Backend (v2):** FastAPI (backend/main.py + backend/routers/)
- **Database:** SQLite with WAL mode (backend/bcp.db or db/bcp.db) — starts empty, user uploads all data
- **ML:** scikit-learn (Ridge, Isolation Forest, GradientBoosting)
- **AI:** Gemini 3.1 Flash Lite via OpenRouter (google/gemini-3.1-flash-lite-preview)
- **Auth:** Session tokens stored in DB + URL query params
- **Container:** Docker on port 8501

## Project Structure
```
app.py                  — Home page (requires login, nav to 4 pages)
config/settings.py      — Sectors, thresholds, energy decision matrix, brand/segment maps
db/                     — SQLite database (empty on first run, auto-created)
utils/database.py       — 20+ tables, WAL mode, all CRUD helpers, auto-migration
utils/auth.py           — Login, roles (super_admin/admin/user), persistent sessions
utils/ai_agent.py       — Agentic AI insights: morning briefing, KPI/table/site analysis, DB-cached (6hr TTL)
utils/email_sender.py   — SMTP alerts, UI-configurable
utils/charts.py         — Plotly chart builders + heatmap color/icon helpers
utils/echarts.py        — ECharts chart builders (bar, line, dual-axis, pie, hbar, grouped, stacked)
utils/smart_table.py    — HTML tables with severity badges + Excel download with icons
utils/kpi_card.py       — KPI cards with calculation transparency
utils/page_header.py    — Consistent dark gradient header across all pages
parsers/blackout_parser.py      — Parses Blackout Hr_ Excel files (CFC, CMHL, CP, PG)
parsers/fuel_price_parser.py    — Parses Daily Fuel Price.xlsx (4 sheets, auto-detects old/new format)
parsers/name_normalizer.py      — Fixes generator name typos
parsers/sales_parser.py         — Parses daily + hourly sales (GOLD_CODE, CostCenter, SegmentName)
parsers/storemaster_parser.py   — Parses store master reference data
parsers/diesel_expense_parser.py — Parses LY diesel expense baseline (old 3-sheet or new single-sheet)
models/decision_engine.py   — Operating modes, delivery queue, budget, anomalies, transfers, load optimization
models/energy_cost.py       — Store economics: blackout-based buffer, date-specific pricing
models/fuel_price_forecast.py — Ridge regression, 7-day price forecast
models/buffer_predictor.py   — Exponential smoothing, stockout projection
models/efficiency_scorer.py  — Isolation Forest anomaly detection
models/bcp_engine.py        — Weighted composite BCP scoring (A-F grades)
models/blackout_predictor.py — GradientBoosting for blackout probability
agents/chat_agent.py    — Tool-calling AI chat with 15 tools
agents/tools/           — data_tools.py (9 query tools), model_tools.py (6 ML tools)
alerts/alert_engine.py  — 11 alert conditions with escalation (incl. energy cost alerts)
pages/05_BCP_Command_Center.py — THE MAIN PAGE: all KPIs, 68 charts, tables, predictions, chart guides
pages/08_BCP_Chat.py           — AI chat agent (chat only)
pages/09_Data_Entry.py         — Upload Excel files (CFC, CMHL, CP, PG, fuel, sales, diesel expense)
pages/10_Settings.py           — User management, SMTP config

### v2 Backend (FastAPI)
backend/main.py             — FastAPI app entry point
backend/routers/upload.py   — /upload/* endpoints (file upload + /upload/validation)
backend/routers/data.py     — /period-kpis, /sector-heatmap, /sector-sites, etc.
backend/routers/charts.py   — Chart data endpoints
backend/routers/auth.py     — Login/logout/session endpoints
backend/routers/config.py   — Config endpoints
backend/routers/ai.py       — AI insight endpoints
backend/routers/insights.py — Insight endpoints
backend/routers/operations.py — Operations endpoints
backend/routers/export.py   — Export endpoints
backend/routers/settings.py — Settings endpoints

### v2 Frontend (SvelteKit)
frontend/src/routes/         — SvelteKit pages (dashboard, upload, chat, login, settings)
frontend/src/lib/components/ — Reusable components:
  AppHeader.svelte           — Top navigation bar
  Chart.svelte               — ECharts wrapper
  MiniChart.svelte           — ECharts sparkline for KPI cards (horizontal bar + 3D avg line)
  KpiCard.svelte             — KPI card with Total + Per Site + daily breakdown chart
  FilterBar.svelte           — Date range + sector filter
  DateFilter.svelte          — Quick date buttons (1D, 3D, 7D, etc.)
  DatePicker.svelte          — Date picker component
  SmartTable.svelte          — Sortable data table
  TabBar.svelte              — Tab navigation
  SiteModal.svelte           — Site detail modal
  ChartGuide.svelte          — Chart explanation card
  Sidebar.svelte             — Left navigation sidebar
  FooterBar.svelte           — Footer
frontend/src/lib/components/sections/ — Dashboard section components
frontend/src/lib/stores/     — Svelte stores (state management)
frontend/src/lib/api.ts      — API client
frontend/src/lib/charts.ts   — Chart config helpers
```

## Page Architecture — BCP Command Center

### Legacy Streamlit (pages/05_BCP_Command_Center.py)
The entire dashboard is ONE page with tabs (see README for full chart inventory).

### v2 SvelteKit Frontend
The new frontend uses a SvelteKit SPA with FastAPI backend:

#### Overview Cockpit (dashboard page):
- **6 KPI Cards** — Gen Hours, Fuel Used, Tank Balance, Blackout Hours, Sales, Diesel Cost
  - Each card: Total value + Per Site value + horizontal bar sparkline (MiniChart.svelte)
  - Daily breakdown bars with 3-day average reference line
  - 1D (last day) vs 3D (avg) comparison in one unified layout
- **3 Derived KPI Cards** — Sales (1D/3D), Fuel Cost (1D/3D), Diesel% (1D/3D)
- **Situation Report** — Auto-generated narrative summary of current status
- No Critical Sites table, no reference card, no separate Prior 3 Days section

#### Sector Heatmap:
- One row per sector with aggregated metrics
- Buffer = last day tank / 3-day avg fuel (NOT AVG of per-site buffer days)

#### Sector Sites (drill-down):
- Full site table with new columns: SALES_1D, SALES_3D, SALES_AVG, COST_1D, COST_3D, COST_AVG, EXP%_1D, EXP%_3D, EXP%_TOTAL, MARGIN%_1D, MARGIN%_3D

#### Upload Page:
- DATA_QUALITY tab — compares Excel totals vs DB totals per date per sector
- Detects issues: time-formatted cells (h:mm), missing SUM formulas
- All upload tabs fit in one line (smaller text)

#### Login Page:
- Show/hide password toggle button

### Filters:
- **Quick Filters** — Yesterday, 3D, 7D, 14D, 30D, 60D, All buttons
- **Date Range** — From/To date inputs with calendar filter
- **Site Type** — All / Regular / LNG dropdown
- All queries respect date filters; /period-kpis accepts date_to param

## Key Patterns

### Parser (blackout_parser.py) — Important Behaviors:
- **Multi-generator same model:** When a site has multiple generators with the same model name, the parser appends `-G2`, `-G3` suffixes to differentiate them
- **Merged seq cells:** The parser checks static columns AND all date columns before skipping a row — a row is only skipped if ALL columns are empty
- **All columns use SUM:** gen_hr, fuel (daily_used), tank (spare_tank_balance), and blackout all use SUM aggregation — matches Excel's SUM() formula behavior
- **Time-formatted cells (h:mm):** Correctly detected and converted to decimal hours (e.g. 5:30 = 5.5 hours)
- **Subtotal rows:** Formula rows (like =SUM()) are automatically detected and skipped during parsing
- **Empty future dates:** Date columns that are entirely empty (unfilled future dates) are skipped — no zero rows generated
- **Tank on ALL generator rows:** Tank balance is stored on every generator row (not deduplicated to first row) — site_summary uses SUM across all generator rows since each row represents a separate drum/tank

### Chart Guide System (`_chart_guide()`):
Every chart has a 4-section guide card rendered below it:
- **Formula** (blue header) — plain English calculation with example numbers
- **Data Source** (green header) — mini table: Data → Excel File → Column → Method (SUM/AVG/LATEST)
- **How to Read** (gold header) — color-coded icons: good, watch, reduce, danger
- **Simple Explanation** (pink header) — real-world analogy for non-technical users with color-highlighted keywords
Uses HTML-like tags: `<c>` cyan columns, `<f>` green files, `<b>` bold, `<g>` green, `<a>` amber, `<r>` red

### Chart number formatting:
- All charts use `_make_rich_data()` in `utils/echarts.py` which formats labels via `{@name}` ECharts pattern
- Numbers: `1.5B`, `36.8M`, `12.3K`, `6,541`, `0.85`
- Sales charts pre-convert to millions (divide by 1e6) before passing to chart
- Dual-axis charts: bar labels shown, line labels hidden (prevent overlap)
- Line charts: labels hidden when >10 points or >2 series
- No JsCode used (streamlit-echarts version doesn't support it)

### Date-specific fuel pricing:
- `_price_on_date(sector_id, date_str)` returns the most recent purchase price on or before that date
- NOT an average of all historical prices — uses the latest price at each point in time
- `_price_history` dict caches all purchase dates/prices per sector

### Blackout-based buffer calculation (legacy):
- Buffer = Tank / (7-day Avg Blackout Hr x Rated L/Hr from generators)
- NOT based on Daily Used (which is refill amount, not actual consumption)
- Joins daily_operations blackout data with generators rated consumption_per_hour

### Buffer calculation (v2 /sector-heatmap):
- Buffer = last day tank / 3-day avg daily fuel
- Calculated at the sector level, not averaged from per-site buffers

### Heatmap icons (no background colors):
- All threshold cells use icons only (green/yellow/orange/red/white circles)
- No background color fills in tables or Excel downloads
- `_get_heatmap_label()` in `utils/charts.py` returns icon + value format

### Agentic AI insights:
- Button-triggered (not auto-run) to control API costs
- 4 insight types: morning_briefing, kpi_insight, table_insight, site_insight
- Gemini 3.1 Flash Lite via OpenRouter (~$0.004/analysis)
- DB-cached with 6-hour TTL in ai_insights_cache table
- Rendered in dark styled boxes with green border

### Database access:
```python
from utils.database import get_db
with get_db() as conn:
    df = pd.read_sql_query("SELECT ...", conn)
```

### Database (utils/database.py) — Key Behaviors:
- **refresh_site_summary:** ALL columns use SUM (gen_hr, fuel, tank, blackout) — was previously MAX for tank and blackout, now SUM because each generator row represents a separate drum/tank
- **Clear data:** Deleting data also deletes generators + sites for clean re-upload (not just daily_operations)

### Authentication:
- Session token in URL: `?session=abc123`
- Token validated against `sessions` table in DB
- Roles: super_admin > admin > user
- Super admin credentials from .env (SUPER_ADMIN_USER/PASS)

### Data upload:
- **No pre-seeded data** — database starts empty, user uploads everything via Data Entry
- Full Replace Mode for ops data: clears daily_operations, site_summary, fuel_purchases, alerts, ai_cache, generators, sites
- Sales data uses upsert (append/update, not full replace)
- Supports: 4 blackout files (CFC, CMHL, CP, PG), 1 fuel price, 1 combo sales file, 1 LY diesel expense
- Auto-detects file type by Excel sheet names
- Fuel price parser auto-detects old format (Date at col 2) vs new format (Date at col 3 with Company column)
- Diesel expense parser handles both old format (3 sector sheets) and new format (single Sheet1 with Sector column)

### Hierarchy from Excel data:
```
business_sector (from Excel) -> company (from Excel) -> site_id -> generator_id
Distribution                    PG                     PG-PGWH    PG-PGWH_100KVA
F&B                            CFC                    CFC-SBFTY  CFC-SBFTY_550 KVA-G1
Property                       CPPL, CMHL SC, UCC     CP-xxx     CP-xxx_model
Retail                         CMHL, MCS              CMHL-xxx   CMHL-xxx_model
```

## Sectors
- **CFC** (City Food Concepts): F&B sector, 2 sites, has blackout data
- **CMHL** (City Mart Holdings): Retail sector, 31 sites, has blackout data
- **CP** (City Properties): Property sector, 25 sites, has blackout data
- **PG** (PG Sector): Distribution sector, 2 sites, has blackout data

## Key Formulas
- **Buffer Days (v2):** `last day tank / 3-day avg daily fuel` (at sector level in /sector-heatmap)
- **Buffer Days (legacy):** `Spare Tank Balance / (7-day Avg Blackout Hr x Rated L/Hr)`
- **Daily Burn:** `SUM(total_daily_used) / COUNT(DISTINCT dates)` (not SQL AVG)
- **Diesel Cost:** `Daily Used x Date-Specific Price` (latest purchase price on/before each date)
- **Diesel % of Sales:** `(Liters x Price) / Sales x 100`
- **Diesel Needed:** `SUM(7 x Avg Burn - Tank)` for sites below 7 days
- **Variance:** `Actual Used - (Rated L/hr x Run Hours)`
- **Efficiency:** `Liters Used / Gen Hours` (normal: flat; spike up = waste/theft)
- **Peak Hours:** `Avg Hourly Sales / Diesel Cost/Hr` (green>3x, yellow>1.5x, orange>1x, red<1x)
- **All KPIs:** SUM across all generator rows per site per date (gen_hr, fuel, tank, blackout)
- **Tank:** SUM of all generator rows — each row represents a separate drum/tank
- **Blackout:** SUM (filled on first row only per site per data entry instructions)
- **3D comparison:** daily averages (not sums) for fair comparison with 1-day values
- **Per Site:** total / number of distinct sites in period

## v2 Backend API Endpoints (key ones)

### /period-kpis
- Accepts `date_to` param, respects calendar filter
- Returns: `recent_daily` (last 4 days of daily data for sparklines), `story` (auto-generated narrative)
- Fields: `total_gen_hr`, `total_fuel`, `total_blackout`, `total_tank`, `tank_per_site`, `fuel_per_site`, `blackout_per_site`, `gen_hr_per_site`
- Uses `fmtN()` helper for narrative number formatting
- Uses `_sanitize()` helper to prevent NaN/Inf JSON serialization errors

### /sector-heatmap
- Buffer = last day tank / 3-day avg fuel (NOT AVG of per-site buffer days)
- One row per sector with aggregated metrics

### /sector-sites
- Site-level drill-down with columns: `last_day_sales`, `avg3d_sales`, `last_day_fuel_cost`, `avg3d_fuel_cost`, `exp_pct_last_day`, `exp_pct_3d`, `exp_pct_total`, `margin_pct_last_day`, `margin_pct_3d`

### /upload/validation
- Compares DB totals vs Excel totals per date per sector
- Detects issues: time-formatted cells (h:mm), missing SUM formulas

## Environment Variables
```
OPENROUTER_API_KEY    — Required for AI features (Gemini 3.1 Flash Lite)
SUPER_ADMIN_USER      — Default: admin
SUPER_ADMIN_PASS      — Default: admin123
SUPER_ADMIN_EMAIL     — Optional
BCP_AGENT_ENABLED     — Default: true
```

## Docker
```bash
docker-compose up -d --build     # Build and run (empty DB, upload data via UI)
docker-compose down              # Stop
docker-compose down -v           # Stop + delete DB volume (full reset)
docker logs city-bcp-agent       # View logs
```
