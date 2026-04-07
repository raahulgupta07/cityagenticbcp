# CityBCPAgent — BCP Command Center

AI-powered Business Continuity Planning dashboard for managing backup generators, fuel supply, and sales-vs-energy profitability across 60+ sites in Myanmar during power outages and diesel shortages.

![Python](https://img.shields.io/badge/Python-3.12-blue) ![Streamlit](https://img.shields.io/badge/Streamlit-1.50-red) ![Gemini](https://img.shields.io/badge/AI-Gemini%203.1%20Flash%20Lite-purple) ![Docker](https://img.shields.io/badge/Docker-Ready-green)

## The Problem

Myanmar faces frequent power outages. Organizations with 60+ outlets need to decide daily:
- **Which outlets can operate?** (full, reduced, generator-only, or close)
- **Where should the fuel truck go first?** (prioritized by urgency)
- **Is the energy cost justified by sales revenue?** (profitability check)
- **Which hours should each store be open?** (peak hours analysis)
- **How much will fuel cost this week?** (budget planning)
- **Is there fuel theft?** (anomaly detection)

## The Solution

A single **BCP Command Center** dashboard that answers all questions with drill-down hierarchy: **Group > Sector > Company > Site**. Database starts empty -- upload your own Excel data via the Data Entry page.

## Dashboard Pages

### v2 Frontend (SvelteKit + FastAPI)
| Page | Purpose |
|---|---|
| **Dashboard** | Overview cockpit: 6 KPI cards with sparklines, sector heatmap, site drill-down |
| **Upload** | Excel upload + DATA_QUALITY tab (Excel vs DB validation per sector) |
| **Chat** | AI chat agent |
| **Login** | Auth with show/hide password toggle |
| **Settings** | User management |

### Legacy Frontend (Streamlit)
| Page | Purpose |
|---|---|
| **BCP Command Center** | THE main page: all KPIs, 68 charts, 15 predictions, heatmaps, operations |
| **BCP Chat** | AI chat agent with 15 tools for natural language queries |
| **Data Entry** | Upload Excel files (CFC, CMHL, CP, PG blackout + fuel + sales) |
| **Settings** | User management, SMTP email config |

## BCP Command Center Features

### Hierarchy: Group > Sector > Company > Site
```
Group (all 60+ sites)
  |-- Distribution (PG) -- PG -- [PG-PGWH, PG-PGMDY]
  |-- F&B (CFC) -- CFC -- [CFC-SBFTY, CFC-BMDY]
  |-- Property (CP) -- CPPL, CMHL SC, UCC -- [25 sites]
  |-- Retail (CMHL) -- CMHL, MCS -- [31 sites]
```

### Date Filters
- Quick buttons: Yesterday, 3 Days, 7 Days, 14 Days, 30 Days, 60 Days, All Data
- From/To date picker
- Site Type filter: All / Regular / LNG
- All charts and KPIs respect selected date range

### KPIs (at every level)
- Days of Diesel Left, Total Tank, Daily Burn, Diesel Needed
- Critical/Warning/Safe site counts, No Data count
- Total Sales, Diesel Cost, Diesel % of Sales
- With formula + source reference on every card

### 68 Charts with Interactive Guides
Every chart includes a 4-section guide card:
- **Formula** -- plain English calculation with real example numbers
- **Data Source** -- which Excel file, which column, aggregation method (SUM/AVG/LATEST)
- **How to Read** -- color-coded interpretation (green/amber/red)
- **Simple Explanation** -- real-world analogy anyone can understand (phone battery, car fuel economy, etc.)

### Chart Categories
| Category | Charts | Description |
|---|---|---|
| Overall Trends | 12 | Gen hours, fuel, efficiency, cost, sales, buffer, blackout |
| Rolling Averages | 15 | 3-day smoothed trends for all metrics |
| By Sector | 6 | Fuel, gen hours, efficiency, cost per sector |
| Sales & Profitability | 4 | Sales vs diesel, diesel %, margin comparison |
| Buffer & Risk | 4 | Buffer days trend, critical sites count |
| Blackout Impact | 3 | Blackout hours, fuel correlation |
| Site Level | 22+ | Deep-dive per site with period selector (Daily/Weekly/Monthly) |

### 15 Predictions & Forecasts
| # | Prediction | Model |
|---|-----------|-------|
| 1 | Fuel Consumption Forecast (7-day) | Linear Regression |
| 2 | Buffer Depletion Timeline | Per-site ranking |
| 3 | Weekly Budget Forecast | Price x Consumption |
| 4 | Blackout Duration Forecast | Linear Trend |
| 5 | Sales Impact (Blackout Correlation) | Dual-axis analysis |
| 6 | Generator Failure Risk | Threshold-based |
| 7 | Optimal Delivery Schedule | Buffer-based urgency |
| 8 | Diesel Price Alert | Ridge Regression forecast |
| 9 | Store Open/Close Recommendation | Diesel% thresholds |
| 10 | Fuel Theft Probability | Anomaly scoring |
| 11 | Efficiency Forecast | Linear Trend |
| 12 | Buffer Days Forecast | Linear Trend |
| 13 | Gen Hours Forecast | Linear Trend |
| 14 | Diesel Cost Forecast | Price x Consumption |
| 15 | Cross-Site Transfer Opportunities | Surplus/deficit matching |

### Agentic AI Insights
- **Morning Briefing** -- URGENT / WATCH / POSITIVE summary with specific site names and actions
- **KPI Analysis** -- 3-sentence interpretation of what KPIs mean for operations
- **Table Analysis** -- which sector needs attention and why
- **Site Analysis** -- 4-line deep-dive on buffer, efficiency, cost vs sales, recommendation
- Powered by Gemini 3.1 Flash Lite via OpenRouter (~$0.004 per analysis)
- Button-triggered (not auto-run), DB-cached with 6-hour TTL

### Operations
- Operating Modes (FULL/REDUCED/CLOSE per site)
- Delivery Queue (urgency + liters + cost)
- BCP Risk Scores (A-F grades)
- Stockout Forecast (7-day)
- Generator Fleet Status
- Maintenance Alerts
- Anomaly Detection (30%+ above average)
- Load Optimization ranking

### Peak Hours Heatmap
- Hour x Day-of-week grid showing profitability vs diesel cost
- Icons: 🟢 PEAK, 🟡 PROFITABLE, 🟠 MARGINAL, 🔴 LOSING
- Auto-recommendation: "Close after 8pm on weekdays"

### Regular vs LNG Comparison
- Side-by-side KPI cards + 6 comparison charts
- Filter by Site Type (All/Regular/LNG)

### Heatmap Tables (icons only)
- 🟢🟡🟠🔴 icons with values -- works in Excel downloads too
- Diesel Price, Blackout Hr, Expense %, Buffer Days thresholds

### Dictionary Tab
- All KPI definitions, formulas, thresholds, icon meanings, data sources
- Operating Mode definitions, BCP Risk Grades, Alert Severity Levels

## Key Calculations

| Metric | Formula | Note |
|---|---|---|
| Buffer Days (v2) | Last day tank / 3-day avg daily fuel | Sector-level in heatmap |
| Buffer Days (legacy) | Tank / (7d Avg Blackout Hr x Rated L/Hr) | Blackout-based, not refill-based |
| All KPIs | SUM across all generator rows per site per date | gen_hr, fuel, tank, blackout all use SUM |
| Tank | SUM of all generator rows | Each row = separate drum/tank |
| Daily Burn | SUM(Daily Used) / COUNT(days) | Not SQL AVG |
| Diesel Cost | Daily Used x Date-Specific Price | Latest purchase price on each date, not historical average |
| Diesel % | (Liters x Price) / Sales x 100 | <0.9% good, <1.5% watch, <3% warning, >3% danger |
| Efficiency | Liters / Gen Hours (L/Hr) | Flat = normal, spike = waste/theft |
| Variance | Actual Used - (Rated L/Hr x Run Hours) | Positive = overconsumption |
| 3D Comparison | Daily averages (not sums) | Fair comparison with 1-day values |

## Quick Start

### Docker (recommended)
```bash
git clone https://github.com/raahulgupta07/CityBCP-CommandCenter.git
cd CityBCPAgentv1
cp .env.example .env
# Edit .env with your OpenRouter API key
docker-compose up -d --build
# Open http://localhost:8501
# Login: admin / admin123
# Upload data via Data Entry page
```

### Local Development
```bash
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

## Data Input

Database starts **empty**. Upload Excel files via Data Entry page. Auto-detects file type by sheet names.

| File | Sheets | Purpose |
|---|---|---|
| Blackout Hr_ CFC.xlsx | `CFC` | CFC generators + fuel + blackout hours |
| Blackout Hr_ CMHL.xlsx | `CMHL` | CMHL generators + fuel + blackout hours |
| Blackout Hr_ CP.xlsx | `CP` | CP generators + fuel + blackout hours |
| Blackout Hr_ PG.xlsx | `PG` | PG generators + fuel + blackout hours |
| Daily Fuel Price.xlsx | `CMHL, CP, CFC, PG` | Fuel purchase prices per supplier |
| CMHL_DAILY_SALES.xlsx | `daily sales, hourly sales, STORE MASTER` | Sales revenue + store master |
| Diesel Expense LY.xlsx | -- | Last year diesel expense baseline |

### Excel Column Reference (Blackout Hr files)
| Column | Description | Used In |
|---|---|---|
| Gen Run Hr | Hours generator ran that day | Efficiency, Gen Hours charts |
| Daily Used | Liters of diesel used/refilled | Fuel burn, cost, buffer calculations |
| Spare Tank Balance | Closing fuel balance in tank (liters) | Buffer days, tank charts |
| Consumption Per Hour | Generator rated L/hr capacity | Buffer calculation, variance |
| Blackout Hr | Hours of power outage | Buffer, blackout charts |

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend (v2) | SvelteKit + ECharts (MiniChart sparklines) |
| Frontend (legacy) | Streamlit 1.50 + streamlit-shadcn-ui 0.1.19 + ECharts |
| Backend (v2) | FastAPI (backend/main.py + routers/) |
| Database | SQLite (WAL mode, 20+ tables, auto-migration) |
| ML | scikit-learn (Ridge, Isolation Forest, Gradient Boosting) |
| AI | Gemini 3.1 Flash Lite via OpenRouter |
| Auth | Session tokens + URL query params |
| Container | Docker on port 8501 |

## Environment Variables
```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
SUPER_ADMIN_USER=admin
SUPER_ADMIN_PASS=change-this-password
SUPER_ADMIN_EMAIL=admin@example.com
BCP_AGENT_ENABLED=true
```

## Project Structure
```
app.py                          -- Home page (Streamlit legacy)
config/settings.py              -- All configuration, thresholds, mappings
pages/05_BCP_Command_Center.py  -- THE main dashboard (~3500 lines, legacy)
pages/08_BCP_Chat.py            -- AI chat agent
pages/09_Data_Entry.py          -- Excel upload (legacy)
pages/10_Settings.py            -- User & email config
utils/                          -- Database, auth, charts, tables, AI, email
models/                         -- Energy cost, predictions, BCP scoring, anomaly detection
parsers/                        -- Excel file parsers (blackout, fuel, sales, expense)
agents/                         -- Chat agent with 15 tools
alerts/                         -- 11 alert conditions with escalation
backend/                        -- FastAPI v2 backend (main.py + routers/)
backend/routers/                -- upload, data, charts, auth, config, ai, etc.
frontend/                       -- SvelteKit v2 frontend
frontend/src/lib/components/    -- KpiCard, MiniChart, SmartTable, Chart, FilterBar, etc.
frontend/src/routes/            -- dashboard, upload, chat, login, settings pages
```

## Parser Behaviors (blackout_parser.py)
- **Multi-generator same model:** Appends -G2, -G3 suffixes to differentiate
- **Merged seq cells:** Checks static + all date columns before skipping
- **All columns use SUM:** gen_hr, fuel, tank, blackout -- matches Excel SUM()
- **Time-formatted cells (h:mm):** Converted to decimal hours (5:30 = 5.5)
- **Subtotal rows:** Formula rows (=SUM()) auto-detected and skipped
- **Empty future dates:** Skipped (no zero rows for unfilled dates)
- **Tank on ALL rows:** Each generator row stores its own tank (separate drum)

## License

Private project for City Holdings Myanmar.
