# CityBCPAgent v1

AI-powered Business Continuity Planning dashboard for generator and fuel management across 55+ sites in Myanmar.

## Features

- **10 Dashboard Pages** — Sector Overview, Site Detail, Fuel Price, Buffer Risk, Power Backup, Generator Fleet, BCP Command Center, AI Insights, Data Entry, Raw Data
- **5 ML Models** — Fuel price forecast, buffer depletion predictor, generator efficiency scorer, BCP composite scoring, blackout pattern detector
- **AI Chat Agent** — 12 tools for natural language queries via Claude Haiku 4.5
- **Excel Upload** — Drop 4 Excel files, system auto-detects type by sheet names, cleans messy data (typos, dashes, formulas)
- **10 Alert Conditions** — Buffer critical, price spike, generator idle, efficiency anomaly, etc.
- **Deep AI Insights** — Full chart/table data sent to LLM for actionable analysis

## Quick Start

### Docker (recommended)
```bash
cp .env.example .env
# Edit .env with your OpenRouter API key
docker compose up -d --build
# Open http://localhost:8501
```

### Local
```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your OpenRouter API key
python seed_database.py
streamlit run app.py
```

## Data Input

Upload the same Excel files your team already uses:
- `Blackout Hr_ CP.xlsx` — City Pharmacy (25 sites)
- `Blackout Hr_ CMHL.xlsx` — City Mart Holdings (30 sites)
- `Blackout Hr_ CFC.xlsx` — City Food Chain (2 factories)
- `Daily Fuel Price.xlsx` — Fuel purchase prices (4 sheets)

File names don't matter — detection is by sheet names inside the Excel.

## Tech Stack

- **Frontend:** Streamlit + streamlit-shadcn-ui + Plotly
- **Database:** SQLite (WAL mode)
- **ML:** scikit-learn (Ridge regression, Isolation Forest, Gradient Boosting)
- **AI:** Claude Haiku 4.5 via OpenRouter
- **Container:** Docker

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes (for AI) | OpenRouter API key for Claude Haiku |

## Project Structure

```
├── app.py                  # Home page
├── config/settings.py      # All configuration
├── utils/                  # Database, charts, tables, AI, LLM client
├── parsers/                # Excel parsers + name normalizer
├── models/                 # 5 ML models
├── agents/                 # Chat agent + 12 tools
├── alerts/                 # 10 alert conditions
├── pages/                  # 10 dashboard pages
├── Data/                   # Excel source files
├── data/                   # SQLite database (auto-generated)
├── Dockerfile
└── compose.yaml
```
