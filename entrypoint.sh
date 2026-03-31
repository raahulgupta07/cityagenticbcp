#!/bin/bash
# Seed database if empty or missing
if [ ! -f /app/data/bcp.db ] || [ $(python3 -c "
import sqlite3
conn = sqlite3.connect('/app/data/bcp.db')
print(conn.execute('SELECT COUNT(*) FROM sites').fetchone()[0])
conn.close()
" 2>/dev/null || echo 0) -eq 0 ]; then
    echo "Seeding database from Excel files..."
    python3 seed_database.py
    echo "Seeding complete."
else
    echo "Database already seeded."
fi

exec streamlit run app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false
