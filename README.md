# CityBCPAgent

AI-powered Business Continuity Planning dashboard for managing backup generators, fuel supply, and sales-vs-energy profitability across 55+ sites in Myanmar during power outages and diesel shortages.

![Python](https://img.shields.io/badge/Python-3.12-blue) ![Streamlit](https://img.shields.io/badge/Streamlit-1.50-red) ![Claude](https://img.shields.io/badge/AI-Claude%20Haiku%204.5-purple) ![Docker](https://img.shields.io/badge/Docker-Ready-green)

## The Problem

Myanmar faces frequent power outages. Organizations with 55+ outlets need to decide daily:
- **Which outlets can operate?** (full, reduced, generator-only, or close)
- **Where should the fuel truck go first?** (prioritized by urgency)
- **Is the energy cost justified by sales revenue?** (profitability check)
- **How much will fuel cost this week?** (budget planning)
- **Which generators need maintenance?** (prevent failures during crisis)

## The Solution

A single dashboard that answers all these questions with AI-powered analysis. Database starts empty -- upload your own Excel data via the Data Entry page.

## Features

### Command Center (the #1 page)
| Feature | What It Does |
|---|---|
| Operating Mode | Recommends FULL/REDUCED/GEN-ONLY/CLOSE per site |
| Delivery Queue | Prioritized list with exact liters, deadline, cost |
| Cost Calculator | Cost per hour per generator, weekly budget forecast |
| Supplier Signal | BUY NOW / WAIT / HOLD based on price trends |
| Maintenance Alerts | Generator failure risk based on cumulative run hours |
| Anomaly Detection | Sites using 30%+ more fuel than normal |
| Resource Sharing | Transfer excess fuel between sectors |
| Load Optimization | Which generator to run at multi-gen sites |
| Recovery Estimate | How fast sites restart after grid power returns |
| What-If Simulator | "What if diesel hits 10,000 MMK?" |

### Store Economics (Sales vs Energy)
| Feature | What It Does |
|---|---|
| Diesel % of Sales | Core KPI -- diesel cost as percentage of revenue per site |
| Per-Site Profitability | Total diesel cost, total sales, margin, recommendation |
| LY Comparison | Current diesel expense vs last 12-month average |
| Sector Pivot | Daily diesel cost, sales, and diesel % by sector and date |

### Dashboard Pages
1. **Command Center** -- CEO daily view: survival KPIs, operating modes, delivery queue, budget, alerts
2. **Store Economics** -- per-site diesel cost vs sales revenue, profitability recommendation
3. **Fuel Price** -- price trends, supplier comparison, 7-day forecast, buy signal
4. **Operations** -- delivery queue, theft detection, generator load optimization
5. **AI Insights** -- chat agent with 15 tools, deep analysis
6. **Data Entry** -- upload Excel files, auto-detect, validate, import with live preview
7. **Settings** -- user management, SMTP email configuration

### 5 ML Models
| Model | Algorithm | Purpose |
|---|---|---|
| Fuel Price Forecast | Ridge Regression | 7-day price prediction |
| Buffer Depletion | Exponential Smoothing | When will sites run out |
| Efficiency Scorer | Isolation Forest | Generator anomaly detection |
| BCP Score Engine | Weighted Composite | Site risk grades A-F |
| Blackout Predictor | Gradient Boosting | Blackout probability |

### AI Agent (Claude Haiku 4.5)
- 15 tools for querying data, running models, comparing energy vs sales
- Natural language: "Which sites have less than 3 days of fuel?"
- Sales queries: "Compare energy cost vs sales for CP sector"
- Deep analysis: sends full chart/table data to LLM
- Each insight shows calculation method + data source

### Authentication & Roles
| Role | Access |
|---|---|
| Super Admin | Everything -- settings, users, upload, analysis |
| Admin | Upload data, run analysis, manage recipients |
| User | View dashboards only (read-only) |

### Email Alerts (11 types)
- Auto-sends after data upload when critical thresholds are breached
- Includes energy cost alerts (when energy > 15% or 30% of sales)
- Pre-configured for Gmail, Outlook, Office 365, Yahoo, SendGrid, Zoho, Amazon SES
- Per-recipient severity + sector filters
- SMTP configured via UI (no .env editing needed)

## Quick Start

### Docker (recommended)
```bash
git clone https://github.com/raahulgupta07/CityBCPAgent.git
cd CityBCPAgent/CityBCPAgentv1
cp .env.example .env
# Edit .env with your OpenRouter API key and super admin credentials
docker compose up -d --build
# Open http://localhost:8501
# Login: admin / admin123 (change in .env before first run)
# Upload your data via Data Entry page
```

### Local Development
```bash
git clone https://github.com/raahulgupta07/CityBCPAgent.git
cd CityBCPAgent/CityBCPAgentv1
pip install -r requirements.txt
cp .env.example .env
# Edit .env
streamlit run app.py
# Upload your data via Data Entry page
```

## Data Input

Database starts **empty** -- upload your Excel files via the Data Entry page. The system auto-detects file types by reading sheet names inside each file. File names don't matter.

### Supported File Types
| File | Sheet Name(s) | Purpose |
|---|---|---|
| Blackout Hr_ CP.xlsx | `CP` | City Properties generator + fuel data |
| Blackout Hr_ CMHL.xlsx | `CMHL` | City Mart Holdings generator + fuel data |
| Blackout Hr_ CFC.xlsx | `CFC` | City Food Concepts generator + fuel data |
| Daily Fuel Price.xlsx | `CMHL, CP, CFC, PG` | Fuel purchase prices per sector |
| CMHL_DAILY_SALES.xlsx | `daily sales, hourly sales, STORE MASTER, mapping` | All-in-one combo sales file |
| Daily Avg Diesel Expense LY.xlsx | `CMHL, CP, CFC` | Last year diesel expense baseline |

### Combo Sales File Format (CMHL_DAILY_SALES.xlsx)
| Sheet | Columns | Purpose |
|---|---|---|
| daily sales | SALES_DATE, GOLD_CODE, CostCenter, SegmentName, SALES_AMT, MARGIN | Daily sales per store per segment |
| hourly sales | DocumentDate, Sales_HR, GOLD_CODE, CostCenter, SegmentName, TotalAmount | Hourly sales breakdown |
| STORE MASTER | 53 columns (GOLD_Code, CostCenter, CostCenterName, SegmentName, Lat/Lng, etc.) | Store reference data |
| mapping | Manual Data, SAP Cost Center Name, SITE_CODE | BCP site name to GOLD_CODE reference |

### Sales-to-BCP Matching (CostCenter Direct Match)

Sales data is matched to BCP (blackout) sites using **CostCenter code** as the direct join key:

```
Blackout Excel  -->  sites.cost_center_code (e.g. 1100007)
Sales Excel     -->  CostCenter column      (e.g. 1100007)
                     Direct match = site_id resolved
```

**No mapping tables or JOINs needed.** The `site_id` is stored directly in `daily_sales` at import time. Backfill runs after every upload, so upload order doesn't matter.

### What the parser handles automatically:
- Generator name typos (KHOLER to KOHLER, HIMONISA to HIMOINSA)
- Dynamic columns (new days = new columns, auto-detected)
- Dashes, blanks, #DIV/0!, text notes cleaned to NULL
- Multi-generator sites aggregated correctly
- Validation: rejects gen hours > 24, keeps rest of data
- GOLD_CODE and CostCenter as site identifiers (new format)
- SegmentName to sector mapping (City Mart to CMHL, City Care to CP, etc.)
- TotalAmount column for hourly sales (new format)

## Environment Variables

```env
# Required for AI features
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# Super Admin (created on first run only)
SUPER_ADMIN_USER=admin
SUPER_ADMIN_PASS=change-this-password
SUPER_ADMIN_EMAIL=admin@company.com
```

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit + streamlit-shadcn-ui + Plotly + ECharts |
| Database | SQLite (WAL mode, 20 tables) |
| ML | scikit-learn (Ridge, Isolation Forest, Gradient Boosting) |
| AI | Claude Haiku 4.5 via OpenRouter |
| Auth | Session tokens in DB + URL params |
| Email | SMTP (configurable via UI) |
| Container | Docker |

## Project Structure

```
app.py                          # Home page
config/settings.py              # All configuration, thresholds, segment/sector maps
db/                             # SQLite database (empty on first run)
utils/
  database.py                   # 20 tables, WAL mode, CRUD, auto-migration
  auth.py                       # Login, roles, persistent sessions
  ai_insights.py                # Deep AI analysis, DB-cached
  llm_client.py                 # OpenRouter + Anthropic client
  email_sender.py               # SMTP email alerts
  charts.py                     # 12 Plotly chart builders
  echarts.py                    # ECharts chart builders
  smart_table.py                # HTML tables with severity badges
  kpi_card.py                   # KPI cards with calculation transparency
  page_header.py                # Consistent gradient headers
parsers/
  blackout_parser.py            # Dynamic Excel column detection
  fuel_price_parser.py          # 4-sheet price parser
  name_normalizer.py            # Generator name typo fixing
  sales_parser.py               # Daily + hourly sales (GOLD_CODE, CostCenter, SegmentName)
  storemaster_parser.py         # Store master reference parser
  diesel_expense_parser.py      # LY diesel expense baseline parser
models/
  decision_engine.py            # 15 Tier 1-3 predictions + energy awareness
  energy_cost.py                # Store economics: direct site_id query, no JOINs
  fuel_price_forecast.py        # Ridge regression, 7-day forecast
  buffer_predictor.py           # Exponential smoothing, stockout
  efficiency_scorer.py          # Isolation Forest anomalies
  bcp_engine.py                 # Weighted composite BCP scores
  blackout_predictor.py         # Gradient Boosting classifier
agents/
  chat_agent.py                 # Tool-calling AI chat
  tools/                        # 15 registered tools (9 data + 6 ML)
alerts/
  alert_engine.py               # 11 alert conditions (incl. energy cost)
pages/                          # Dashboard pages
Dockerfile
docker-compose.yml
seed_database.py                # One-time seed script (optional, for dev)
```

## Database Schema (20 tables)

| Table | Purpose |
|---|---|
| users | Authentication + roles |
| sectors | CP, CMHL, CFC, PG |
| sites | BCP outlet locations (with cost_center_code from blackout) |
| generators | Generator models per site |
| daily_operations | Per-generator per-day fact table |
| daily_site_summary | Materialized view: buffer days, totals |
| fuel_purchases | Diesel prices from suppliers |
| store_master | Sales system store reference (GOLD_Code, CostCenter, segment) |
| daily_sales | Daily sales per site (with site_id resolved via CostCenter) |
| hourly_sales | Hourly sales (with site_id resolved via CostCenter) |
| site_sales_map | Legacy mapping table (kept for backward compat) |
| diesel_expense_ly | Last year diesel expense baseline |
| alerts | Auto-generated threshold alerts |
| alert_recipients | Email notification targets |
| email_log | Delivery audit trail |
| app_settings | SMTP config, preferences |
| ai_insights_cache | Persisted AI analysis |
| upload_history | File import audit |
| generator_name_map | Typo to canonical name mapping |
| incidents | Manual incident logging |

## Energy Cost Thresholds

| Diesel % of Sales | Status | Recommendation |
|---|---|---|
| < 5% | HEALTHY | Full operations |
| 5-15% | MONITOR | Review generator schedules |
| 15-30% | REDUCE | Cut generator hours |
| 30-60% | CRITICAL | Essential hours only |
| > 60% | CLOSE | Temporary closure recommended |

## License

Private project for City Holdings Myanmar.
