"""
Shared page header — gradient card matching the home page style.
Use on every page for consistent look.
"""
import streamlit as st
from utils.auth import get_current_user
from utils.database import get_db


def render_page_header(icon, title, description):
    """Render gradient header card like the home page."""
    user = get_current_user()
    user_name = user["display_name"] if user else ""

    # Get latest data date
    try:
        with get_db() as conn:
            row = conn.execute("SELECT MAX(date) FROM daily_site_summary").fetchone()
            data_date = row[0] if row and row[0] else "N/A"
    except Exception:
        data_date = "N/A"

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#0f172a,#1e3a5f);border-radius:16px;
                padding:28px 32px;color:white;margin-bottom:20px">
        <div style="display:flex;justify-content:space-between;align-items:center">
            <div>
                <h1 style="margin:0;font-size:24px;font-weight:700">{icon} {title}</h1>
                <p style="margin:6px 0 0;opacity:0.7;font-size:13px">{description}</p>
            </div>
            <div style="text-align:right;opacity:0.5;font-size:11px">
                {user_name}<br>Data through {data_date}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
