# CLAUDE.md — Project Guide for AI Assistants

## What is this project?

CityBCPAgent is a Business Continuity Planning dashboard for managing backup generators and fuel supply across 55+ sites in Myanmar. It helps decision-makers during power outages and diesel shortages. It compares energy (fuel) costs against sales revenue to recommend whether stores should stay open.

## Tech Stack
- **Frontend:** Streamlit 1.50 + streamlit-shadcn-ui 0.1.19 + Plotly + ECharts
- **Database:** SQLite with WAL mode (db/bcp.db) — starts empty, user uploads all data
- **ML:** scikit-learn (Ridge, Isolation Forest, GradientBoosting)
- **AI:** Claude Haiku 4.5 via OpenRouter (cheapest Claude model)
- **Auth:** Session tokens stored in DB + URL query params
- **Container:** Docker on port 8501

## Project Structure
```
app.py                  — Home page (requires login)
config/settings.py      — Sectors, thresholds, energy decision matrix, brand/segment maps
db/                     — SQLite database (empty on first run, auto-created)
utils/database.py       — 20 tables, WAL mode, all CRUD helpers, auto-migration
utils/auth.py           — Login, roles (super_admin/admin/user), persistent sessions
utils/ai_insights.py    — AI analysis: DB-cached, one-button generation per page
utils/llm_client.py     — OpenRouter (primary) + Anthropic (fallback) LLM client
utils/email_sender.py   — SMTP alerts, UI-configurable
utils/charts.py         — 12 reusable Plotly chart builders
utils/echarts.py        — ECharts chart builders
utils/smart_table.py    — HTML tables with severity badges
utils/kpi_card.py       — KPI cards with calculation transparency
utils/page_header.py    — Consistent dark gradient header across all pages
parsers/blackout_parser.py      — Parses Blackout Hr_ Excel files (dynamic columns)
parsers/fuel_price_parser.py    — Parses Daily Fuel Price.xlsx (4 sheets)
parsers/name_normalizer.py      — Fixes generator name typos
parsers/sales_parser.py         — Parses daily + hourly sales (GOLD_CODE, CostCenter, SegmentName)
parsers/storemaster_parser.py   — Parses store master reference data
parsers/diesel_expense_parser.py — Parses LY diesel expense baseline
models/decision_engine.py   — 15 Tier 1-3 predictions + energy-aware operating modes
models/energy_cost.py       — Store economics: direct site_id query, no JOINs
models/fuel_price_forecast.py — Ridge regression, 7-day price forecast
models/buffer_predictor.py   — Exponential smoothing, stockout projection
models/efficiency_scorer.py  — Isolation Forest anomaly detection
models/bcp_engine.py        — Weighted composite BCP scoring (A-F grades)
models/blackout_predictor.py — GradientBoosting for blackout probability
agents/chat_agent.py    — Tool-calling AI chat with 15 tools
agents/tools/           — data_tools.py (9 query tools), model_tools.py (6 ML tools)
alerts/alert_engine.py  — 11 alert conditions with escalation (incl. energy cost alerts)
pages/00_Command_Center.py  — CEO daily view: KPIs, modes, delivery, budget, alerts
pages/01_Store_Economics.py — Sales vs Energy: per-site profitability
pages/03_Fuel_Price.py      — Price trends, forecast, buy signals
pages/03_Operations.py      — Delivery queue, theft detection, load optimization
pages/08_AI_Insights.py     — AI chat agent interface
pages/09_Data_Entry.py      — Upload Excel files, auto-detect, validate, import
pages/10_Settings.py        — User management, SMTP config
seed_database.py        — One-time Excel → SQLite migration (not used in Docker)
```

## Key Patterns

### Every page follows this pattern:
```python
import sys; sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.auth import require_login, render_sidebar_user
from utils.page_header import render_page_header
from utils.ai_insights import render_insight_panel, finish_page

st.set_page_config(...)
require_login()
render_sidebar_user()
render_page_header(icon, title, description)

# ... page content with charts, tables ...
render_insight_panel(context, data, unique_key)  # after each chart/table

finish_page()  # at the very end — shows AI generate button
```

### Database access:
```python
from utils.database import get_db
with get_db() as conn:
    df = pd.read_sql_query("SELECT ...", conn)
```

### AI insights:
- `render_insight_panel()` queues for generation
- `render_page_summary()` queues page-level summary
- `finish_page()` shows the "Generate AI Analysis" button
- Insights are cached in `ai_insights_cache` DB table with timestamps
- "Refresh All Analysis" clears cache and regenerates

### Authentication:
- Session token in URL: `?session=abc123`
- Token validated against `sessions` table in DB
- Survives browser refresh (24hr expiry)
- Roles: super_admin > admin > user
- Super admin credentials from .env (SUPER_ADMIN_USER/PASS)

### Data upload:
- **No pre-seeded data** — database starts empty, user uploads everything via Data Entry
- Full Replace Mode for ops data: clears daily_operations, site_summary, fuel_purchases, alerts, ai_cache
- Sales data uses upsert (append/update, not full replace)
- Keeps: sites, generators, users, settings (structural data)
- Auto-detects file type by Excel sheet names (not filename)
- Supports: 3 blackout files, 1 fuel price, 1 combo sales file (daily+hourly+store master+mapping), 1 LY diesel expense
- Auto-runs alerts after import
- Auto-sends email if SMTP configured

### Sales-to-BCP Site Matching (CostCenter direct match):
The system matches sales data to BCP (blackout) sites using **CostCenter code** as the direct join key:

```
Blackout Excel → sites.cost_center_code (e.g. 1100007)
Sales Excel → daily_sales CostCenter column (e.g. 1100007)
Match: sites.cost_center_code = sales.CostCenter → site_id resolved
```

**No JOIN tables needed.** The `site_id` is stored directly in `daily_sales` and `hourly_sales` at import time.

**Backfill on every upload:** After any file import (blackout or sales), the system backfills `site_id` into sales rows using:
1. `store_master.gold_code` → `store_master.cost_center_code` → `sites.cost_center_code`
2. This handles upload order independence (sales before or after blackout)

### Store Economics (energy_cost.py):
- Queries `daily_sales WHERE site_id IS NOT NULL GROUP BY site_id` — no site_sales_map JOIN
- `energy_cost = total_liters × avg_fuel_price`
- `diesel_pct = (energy_cost / total_sales) × 100`
- Decision matrix: <5% OPEN, 5-15% MONITOR, 15-30% REDUCE, >30% CLOSE

### Sales Parser (new format):
The combo sales file (`CMHL_DAILY_SALES.xlsx`) has these sheets:
- **daily sales**: SALES_DATE, GOLD_CODE, CostCenter, SegmentName, SALES_AMT, MARGIN
- **hourly sales**: DocumentDate, Sales_HR, GOLD_CODE, CostCenter, SegmentName, TotalAmount
- **STORE MASTER**: 53-column rich store metadata (GOLD_Code, CostCenter, CostCenterName, etc.)
- **mapping**: Manual Data → SAP Cost Center Name → SITE_CODE (reference only)

Parser handles both old format (Site Name, Brand) and new format (GOLD_CODE, SegmentName, TotalAmount).

## Sectors
- **CP** (City Properties): has blackout data
- **CMHL** (City Mart Holdings): no blackout tracking
- **CFC** (City Food Concepts): has blackout tracking but mostly NULL
- **PG**: No active data

## Segment → Sector Mapping
SegmentName from sales files maps to sectors:
- City Mart, Ocean, Market Place, miniCityMart, City Baby Club, City Book & Music, Safari, E COMMERCE → **CMHL**
- City Care, City Express, City Express Franchise → **CP**
- Canteen → **CFC**

## Data Flow
```
Excel files → Parser (clean/validate) → SQLite DB
                                          ├── daily_sales (site_id resolved via CostCenter)
                                          ├── daily_operations (from blackout files)
                                          └── fuel_purchases (from fuel price file)
                                                ↓
Dashboard pages ← energy_cost.py queries daily_sales by site_id directly
                ← ML Models → Predictions
                ← AI Agent → Deep insights
                ← Alert Engine → Email alerts
```

## Common Tasks

### Add a new page:
1. Create `pages/XX_Name.py`
2. Follow the pattern above (auth + header + content + finish_page)
3. Add navigation entry in `app.py` NAV list

### Add a new ML model:
1. Create `models/new_model.py` with a main function
2. Add a tool in `agents/tools/model_tools.py` using @tool decorator
3. Call from relevant page

### Add a new alert condition:
1. Add check function in `alerts/alert_engine.py`
2. Call it from `run_all_checks()`
3. Add threshold to `config/settings.py` ALERTS dict

### Add a new database table:
1. Add CREATE TABLE to SCHEMA string in `utils/database.py`
2. Add migration in `init_db()` for existing DBs (ALTER TABLE)
3. Add CRUD helpers below
4. Table auto-creates on next run (init_db runs on import)

## Key Formulas

### Buffer calculation:
- **Correct:** `SUM(spare_tank_balance) / NULLIF(SUM(total_daily_used), 0)` at sector level
- **Wrong:** `AVG(days_of_buffer)` — cannot average ratios, outliers skew results

### Efficiency calculation:
- `efficiency = actual_used / (rated_consumption * run_hours)`
- Normal range: 0.8-1.2. Anomaly: <0.5 or >1.5

### Energy cost calculation:
- `energy_cost = daily_used_liters * fuel_price_per_liter`
- `energy_pct = (energy_cost / sales_value) * 100`
- Thresholds: <5% HEALTHY, 5-15% MONITOR, 15-30% REDUCE, 30-60% CRITICAL, >60% CLOSE

## Environment Variables
```
OPENROUTER_API_KEY    — Required for AI features
SUPER_ADMIN_USER      — Default: admin
SUPER_ADMIN_PASS      — Default: admin123
SUPER_ADMIN_EMAIL     — Optional
```

## Docker
```bash
docker compose up -d --build     # Build and run (empty DB, upload data via UI)
docker compose down              # Stop
docker compose down -v           # Stop + delete DB volume (full reset)
docker logs city-bcp-agent       # View logs
docker exec city-bcp-agent python3 -c "..."  # Run commands inside
```
