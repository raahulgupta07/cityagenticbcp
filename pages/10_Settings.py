"""
Page 10: Settings — User management, email config, system settings
Super Admin: full access | Admin: alert recipients only | User: no access
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import streamlit_shadcn_ui as ui
import pandas as pd
from utils.database import get_db, get_setting, set_setting
from utils.page_header import render_page_header
from utils.auth import (
    require_login, require_role, has_permission, get_current_user,
    render_sidebar_user, ROLES, create_user, list_users, update_user, delete_user,
    hash_password,
)
from utils.email_sender import get_smtp_config, send_test_email, is_email_configured, send_alert_email
from alerts.alert_engine import get_active_alerts
from config.settings import SECTORS

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")

# Auth
require_login()
render_sidebar_user()

user = get_current_user()
is_super = user["role"] == "super_admin"
is_admin = user["role"] in ("super_admin", "admin")

if not is_admin:
    st.error("Access denied. Admin or Super Admin role required.")
    st.stop()

render_page_header("⚙️", "Settings", "User management, email configuration, and system settings")

# Tabs based on role
if is_super:
    tab_options = ["👥 User Management", "📧 Email Setup", "👤 Recipients", "📬 Email Log", "🔧 System"]
else:
    tab_options = ["👤 Recipients", "📬 Email Log"]

selected = ui.tabs(options=tab_options, default_value=tab_options[0], key="settings_tabs")

# ═══════════════════════════════════════════════════════════════════════════
# USER MANAGEMENT (Super Admin only)
# ═══════════════════════════════════════════════════════════════════════════
if selected == "👥 User Management" and is_super:
    st.markdown("### User Management")
    ui.alert(
        title="👥 Manage Users",
        description="Super Admin creates Admins and Users. Admins can upload data and run analysis. Users can only view dashboards.",
        key="alert_users",
    )

    # Current users
    users_df = list_users()
    if not users_df.empty:
        st.markdown("#### Current Users")
        display = users_df[["username", "display_name", "email", "role", "is_active", "last_login", "created_by"]].copy()
        display["role"] = display["role"].map({r: info["label"] for r, info in ROLES.items()})
        display["is_active"] = display["is_active"].apply(lambda x: "✅ Active" if x else "❌ Disabled")
        display.columns = ["Username", "Name", "Email", "Role", "Status", "Last Login", "Created By"]
        st.dataframe(display, use_container_width=True, hide_index=True)

    # Create new user
    st.markdown("#### Create New User")
    with st.form("create_user_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            new_username = st.text_input("Username", placeholder="john.doe")
            new_password = st.text_input("Password", type="password", placeholder="Min 6 characters")
        with c2:
            new_name = st.text_input("Display Name", placeholder="John Doe")
            new_email = st.text_input("Email", placeholder="john@company.com")
        with c3:
            # Super admin can create admin and user. Admin can only create user.
            new_role = st.selectbox("Role", ["admin", "user"],
                                     format_func=lambda r: ROLES[r]["label"])
            new_sectors = st.multiselect("Sector Access (empty = all)", list(SECTORS.keys()))

        if st.form_submit_button("➕ Create User", use_container_width=True):
            if not new_username or not new_password or not new_name:
                st.error("Username, password, and name are required")
            elif len(new_password) < 6:
                st.error("Password must be at least 6 characters")
            else:
                success, error = create_user(
                    new_username, new_password, new_name, new_email,
                    new_role, new_sectors, user["username"]
                )
                if success:
                    st.success(f"✅ User '{new_username}' created as {ROLES[new_role]['label']}")
                    st.rerun()
                else:
                    st.error(error)

    # Manage existing users
    if not users_df.empty and len(users_df) > 1:
        st.markdown("#### Manage Users")
        # Exclude current user from management
        manageable = users_df[users_df["username"] != user["username"]]
        if not manageable.empty:
            selected_user = st.selectbox(
                "Select user",
                manageable["id"].tolist(),
                format_func=lambda x: f"{manageable[manageable['id']==x].iloc[0]['display_name']} ({manageable[manageable['id']==x].iloc[0]['username']}) — {manageable[manageable['id']==x].iloc[0]['role']}",
                key="manage_user_select",
            )

            mc1, mc2, mc3, mc4 = st.columns(4)
            with mc1:
                if st.button("🔄 Toggle Active", key="btn_toggle_user"):
                    row = manageable[manageable["id"] == selected_user].iloc[0]
                    update_user(selected_user, is_active=0 if row["is_active"] else 1)
                    st.rerun()
            with mc2:
                new_role_change = st.selectbox("Change Role", ["admin", "user"],
                                                key="change_role_select")
                if st.button("💼 Update Role", key="btn_change_role"):
                    update_user(selected_user, role=new_role_change)
                    st.rerun()
            with mc3:
                new_pass = st.text_input("New Password", type="password", key="reset_pass")
                if st.button("🔑 Reset Password", key="btn_reset_pass"):
                    if new_pass and len(new_pass) >= 6:
                        update_user(selected_user, password=new_pass)
                        st.success("Password reset")
                    else:
                        st.error("Min 6 characters")
            with mc4:
                st.markdown("")
                if st.button("🗑️ Delete User", key="btn_delete_user"):
                    delete_user(selected_user)
                    st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# EMAIL SETUP (Super Admin only)
# ═══════════════════════════════════════════════════════════════════════════
elif selected == "📧 Email Setup" and is_super:
    st.markdown("### Email Configuration")

    # ─── Preset selector ─────────────────────────────────────────────────
    st.markdown("#### Quick Setup — Choose Your Email Provider")

    PRESETS = {
        "Custom": {"server": "", "port": 587, "tls": True},
        "Gmail": {"server": "smtp.gmail.com", "port": 587, "tls": True},
        "Outlook / Hotmail": {"server": "smtp-mail.outlook.com", "port": 587, "tls": True},
        "Office 365": {"server": "smtp.office365.com", "port": 587, "tls": True},
        "Yahoo Mail": {"server": "smtp.mail.yahoo.com", "port": 587, "tls": True},
        "SendGrid": {"server": "smtp.sendgrid.net", "port": 587, "tls": True},
        "Zoho Mail": {"server": "smtp.zoho.com", "port": 587, "tls": True},
        "Amazon SES": {"server": "email-smtp.us-east-1.amazonaws.com", "port": 587, "tls": True},
    }

    preset = st.selectbox("Email Provider", list(PRESETS.keys()), key="email_preset")
    preset_config = PRESETS[preset]

    if preset == "Gmail":
        st.info("**Gmail Setup:** Go to [Google App Passwords](https://myaccount.google.com/apppasswords), generate an app password, and use it below. Do NOT use your regular Gmail password.")
    elif preset in ("Outlook / Hotmail", "Office 365"):
        st.info("**Microsoft Setup:** Use your email address as username. If 2FA is enabled, create an [App Password](https://account.live.com/proofs/manage/additional).")

    # Load current config
    config = get_smtp_config()

    with st.form("smtp_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            smtp_server = st.text_input("SMTP Server",
                                         value=preset_config["server"] if preset != "Custom" else config["server"],
                                         placeholder="smtp.gmail.com")
        with c2:
            smtp_port = st.number_input("Port",
                                         value=preset_config["port"] if preset != "Custom" else config["port"],
                                         min_value=1, max_value=65535)
        with c3:
            use_tls = st.checkbox("Use TLS", value=preset_config["tls"] if preset != "Custom" else config["use_tls"])

        c4, c5 = st.columns(2)
        with c4:
            smtp_user = st.text_input("Username / Email", value=config["username"],
                                       placeholder="your@email.com")
        with c5:
            smtp_pass = st.text_input("Password / App Password", value=config["password"],
                                       type="password", placeholder="App password")

        c6, c7 = st.columns(2)
        with c6:
            sender_name = st.text_input("Sender Name", value=config["sender_name"] or "CityBCPAgent")
        with c7:
            sender_email = st.text_input("Sender Email", value=config["sender_email"] or smtp_user,
                                          placeholder="Same as username for most providers")

        enabled = st.checkbox("✅ Enable Email Alerts", value=config["enabled"])

        if st.form_submit_button("💾 Save Email Settings", use_container_width=True):
            set_setting("smtp_server", smtp_server)
            set_setting("smtp_port", str(smtp_port))
            set_setting("smtp_username", smtp_user)
            set_setting("smtp_password", smtp_pass)
            set_setting("smtp_sender_name", sender_name)
            set_setting("smtp_sender_email", sender_email or smtp_user)
            set_setting("smtp_use_tls", "true" if use_tls else "false")
            set_setting("smtp_enabled", "true" if enabled else "false")
            set_setting("smtp_provider", preset)
            st.success(f"✅ Email settings saved! Provider: {preset}")

    # Test email
    st.markdown("---")
    st.markdown("#### Test Email")
    tc1, tc2 = st.columns([3, 1])
    with tc1:
        test_to = st.text_input("Send test to", placeholder="your@email.com", key="test_email")
    with tc2:
        st.markdown("")
        if st.button("📨 Send Test", key="btn_test"):
            if test_to:
                with st.spinner("Sending..."):
                    ok, err = send_test_email(test_to)
                st.success(f"✅ Sent to {test_to}") if ok else st.error(f"❌ {err}")
            else:
                st.warning("Enter email address")

    # Status
    st.markdown("---")
    if is_email_configured():
        provider = get_setting("smtp_provider", "Custom")
        ui.badges(badge_list=[("Email", "default"), ("ENABLED", "default"), (provider, "secondary")],
                  key="badge_email_status")
    else:
        ui.badges(badge_list=[("Email", "destructive"), ("NOT CONFIGURED", "outline")],
                  key="badge_email_status")

# ═══════════════════════════════════════════════════════════════════════════
# RECIPIENTS (Admin + Super Admin)
# ═══════════════════════════════════════════════════════════════════════════
elif selected == "👤 Recipients":
    st.markdown("### Alert Recipients")
    st.caption("People who receive email alerts when critical conditions are detected.")

    with get_db() as conn:
        recipients = pd.read_sql_query("SELECT * FROM alert_recipients ORDER BY is_active DESC, name", conn)

    if not recipients.empty:
        display = recipients[["name", "email", "role", "sectors", "severity_filter", "is_active"]].copy()
        display["is_active"] = display["is_active"].apply(lambda x: "✅" if x else "❌")
        display.columns = ["Name", "Email", "Role", "Sectors", "Alerts", "Active"]
        st.dataframe(display, use_container_width=True, hide_index=True)

    with st.form("add_recipient", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            r_name = st.text_input("Name", placeholder="John Doe")
        with c2:
            r_email = st.text_input("Email", placeholder="john@company.com")
        with c3:
            r_role = st.selectbox("Role", ["Sector Lead", "Manager", "Director", "IT Admin"])

        c4, c5 = st.columns(2)
        with c4:
            r_sectors = st.multiselect("Sectors (empty = all)", list(SECTORS.keys()))
        with c5:
            r_severity = st.multiselect("Alert Types", ["CRITICAL", "WARNING", "INFO"],
                                         default=["CRITICAL", "WARNING"])

        if st.form_submit_button("➕ Add Recipient", use_container_width=True):
            if r_name and r_email:
                with get_db() as conn:
                    conn.execute("""
                        INSERT INTO alert_recipients (name, email, role, sectors, severity_filter)
                        VALUES (?, ?, ?, ?, ?)
                    """, (r_name, r_email, r_role,
                          ",".join(r_sectors) if r_sectors else None,
                          ",".join(r_severity)))
                st.success(f"✅ Added {r_name}")
                st.rerun()

    if not recipients.empty:
        st.markdown("#### Manage")
        c1, c2 = st.columns([3, 1])
        with c1:
            r_select = st.selectbox("Select",
                                     recipients["id"].tolist(),
                                     format_func=lambda x: f"{recipients[recipients['id']==x].iloc[0]['name']} ({recipients[recipients['id']==x].iloc[0]['email']})",
                                     key="manage_r")
        with c2:
            bc1, bc2 = st.columns(2)
            with bc1:
                if st.button("🔄", key="btn_toggle_r", help="Toggle active"):
                    with get_db() as conn:
                        conn.execute("UPDATE alert_recipients SET is_active = CASE WHEN is_active=1 THEN 0 ELSE 1 END WHERE id=?", (r_select,))
                    st.rerun()
            with bc2:
                if st.button("🗑️", key="btn_del_r", help="Delete"):
                    with get_db() as conn:
                        conn.execute("DELETE FROM alert_recipients WHERE id=?", (r_select,))
                    st.rerun()

    # Send now
    st.markdown("---")
    if st.button("🚨 Send Current Alerts Now", key="btn_send_now", type="primary", use_container_width=True):
        if not is_email_configured():
            st.error("Email not configured. Ask Super Admin to set up SMTP.")
        else:
            alerts = get_active_alerts()
            if alerts.empty:
                st.info("No active alerts.")
            else:
                with st.spinner("Sending..."):
                    sent, errors = send_alert_email(alerts)
                st.success(f"✅ Sent to {sent} recipient(s)") if sent else None
                for e in errors:
                    st.error(e)

# ═══════════════════════════════════════════════════════════════════════════
# EMAIL LOG
# ═══════════════════════════════════════════════════════════════════════════
elif selected == "📬 Email Log":
    st.markdown("### Email Log")
    with get_db() as conn:
        logs = pd.read_sql_query("SELECT * FROM email_log ORDER BY sent_at DESC LIMIT 50", conn)

    if not logs.empty:
        c1, c2 = st.columns(2)
        with c1:
            ui.metric_card(title="Sent", content=str(len(logs[logs["status"]=="sent"])),
                           description="successful", key="mc_log_sent")
        with c2:
            ui.metric_card(title="Failed", content=str(len(logs[logs["status"]=="failed"])),
                           description="errors", key="mc_log_fail")
        st.dataframe(logs[["recipient", "subject", "alert_count", "status", "sent_at"]],
                     use_container_width=True, hide_index=True)
    else:
        st.info("No emails sent yet.")

# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM (Super Admin only)
# ═══════════════════════════════════════════════════════════════════════════
elif selected == "🔧 System" and is_super:
    st.markdown("### System")

    with get_db() as conn:
        tables = {}
        for t in ["users", "sectors", "sites", "generators", "daily_operations",
                   "fuel_purchases", "daily_site_summary", "alerts",
                   "alert_recipients", "email_log", "ai_insights_cache", "app_settings", "upload_history"]:
            try:
                tables[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except Exception:
                tables[t] = 0

    for name, count in tables.items():
        st.caption(f"**{name}**: {count:,} rows")

    st.markdown("---")
    st.markdown("#### Danger Zone")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🗑️ Clear AI Cache", key="btn_clr_ai"):
            with get_db() as conn:
                conn.execute("DELETE FROM ai_insights_cache")
            st.success("Cleared")
    with c2:
        if st.button("🗑️ Clear Alerts", key="btn_clr_alerts"):
            with get_db() as conn:
                conn.execute("DELETE FROM alerts")
            st.success("Cleared")
    with c3:
        if st.button("🗑️ Clear Email Log", key="btn_clr_email"):
            with get_db() as conn:
                conn.execute("DELETE FROM email_log")
            st.success("Cleared")
