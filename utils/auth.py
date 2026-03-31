"""
Authentication & Authorization — Role-based access control.
Session persists across browser refreshes via DB-stored token + cookie.

Roles:
  super_admin — Full access: settings, user management, upload, analysis, view
  admin       — Upload data, run analysis, view all, manage alert recipients
  user        — View dashboards and analysis only (read-only)
"""
import streamlit as st
import hashlib
import secrets
from datetime import datetime, timedelta
from utils.database import get_db

# ─── Role Definitions ────────────────────────────────────────────────────────

ROLES = {
    "super_admin": {
        "label": "Super Admin",
        "description": "Full access — settings, users, upload, analysis, view",
        "can_manage_users": True,
        "can_manage_settings": True,
        "can_upload": True,
        "can_edit_data": True,
        "can_view": True,
    },
    "admin": {
        "label": "Admin",
        "description": "Upload data, run analysis, manage recipients, view all",
        "can_manage_users": False,
        "can_manage_settings": False,
        "can_upload": True,
        "can_edit_data": True,
        "can_view": True,
    },
    "user": {
        "label": "User",
        "description": "View dashboards and analysis only (read-only)",
        "can_manage_users": False,
        "can_manage_settings": False,
        "can_upload": False,
        "can_edit_data": False,
        "can_view": True,
    },
}

# Which pages each role can access
PAGE_ACCESS = {
    "super_admin": ["all"],
    "admin": ["Raw Data", "Sector Overview", "Site Detail", "Fuel Price",
              "Buffer Risk", "Blackout Monitor", "Generator Fleet",
              "BCP Scores", "AI Insights", "Data Entry"],
    "user": ["Raw Data", "Sector Overview", "Site Detail", "Fuel Price",
             "Buffer Risk", "Blackout Monitor", "Generator Fleet",
             "BCP Scores", "AI Insights"],
}


# ─── Password Hashing ───────────────────────────────────────────────────────

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password, password_hash):
    return hash_password(password) == password_hash


# ─── Session Token Management (survives browser refresh) ─────────────────────

def _create_session_token(user_id):
    """Create a session token, store in DB, return token string."""
    token = secrets.token_hex(32)
    expires = (datetime.now() + timedelta(hours=24)).isoformat()
    with get_db() as conn:
        # Create sessions table if not exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        # Clean expired sessions
        conn.execute("DELETE FROM sessions WHERE expires_at < datetime('now')")
        # Insert new session
        conn.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
                     (token, user_id, expires))
    return token


def _validate_session_token(token):
    """Check if token is valid and not expired. Returns user dict or None."""
    if not token:
        return None
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        row = conn.execute("""
            SELECT u.* FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ? AND s.expires_at > datetime('now') AND u.is_active = 1
        """, (token,)).fetchone()
    if row:
        return {
            "id": row["id"], "username": row["username"],
            "display_name": row["display_name"], "email": row["email"],
            "role": row["role"], "sectors": row["sectors"],
        }
    return None


def _delete_session_token(token):
    """Remove session token from DB."""
    if token:
        with get_db() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER, expires_at TEXT, created_at TEXT)")
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def get_current_user():
    """Get current logged-in user. Checks session state first, then cookie/query param."""
    # 1. Check session state (fastest)
    if "user" in st.session_state and st.session_state["user"]:
        return st.session_state["user"]

    # 2. Check query param token (survives refresh)
    token = st.query_params.get("session", None)
    if token:
        user = _validate_session_token(token)
        if user:
            st.session_state["user"] = user
            return user
        else:
            # Token expired or invalid — clear it
            st.query_params.clear()

    return None


def is_logged_in():
    return get_current_user() is not None


def get_user_role():
    user = get_current_user()
    return user["role"] if user else None


def has_permission(permission):
    """Check if current user has a specific permission."""
    role = get_user_role()
    if not role:
        return False
    role_info = ROLES.get(role, {})
    return role_info.get(permission, False)


def can_access_page(page_name):
    """Check if current user can access a page."""
    role = get_user_role()
    if not role:
        return False
    allowed = PAGE_ACCESS.get(role, [])
    return "all" in allowed or page_name in allowed


def require_login():
    """Call at the top of every page. Shows login if not authenticated."""
    if is_logged_in():
        return True

    _show_login_form()
    st.stop()
    return False


def require_role(min_role):
    """Require at least this role level. super_admin > admin > user."""
    if not is_logged_in():
        _show_login_form()
        st.stop()
        return False

    role_order = {"super_admin": 3, "admin": 2, "user": 1}
    current = role_order.get(get_user_role(), 0)
    required = role_order.get(min_role, 0)

    if current < required:
        st.error(f"Access denied. You need **{ROLES[min_role]['label']}** role or higher.")
        st.stop()
        return False
    return True


def logout():
    token = st.query_params.get("session", None)
    _delete_session_token(token)
    st.session_state.pop("user", None)
    st.query_params.clear()


# ─── Login Form ──────────────────────────────────────────────────────────────

def _show_login_form():
    # Hide sidebar, header, footer — full clean screen
    st.markdown("""
    <style>
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="stSidebarCollapsedControl"] { display: none !important; }
        header[data-testid="stHeader"] { display: none !important; }
        footer { display: none !important; }
        #MainMenu { display: none !important; }
        html, body, [data-testid="stAppViewContainer"] {
            overflow: hidden !important;
            height: 100vh !important;
        }
        .block-container {
            padding: 0 !important;
            max-width: 100% !important;
            height: 100vh !important;
            overflow: hidden !important;
        }
        /* Dark background */
        [data-testid="stAppViewContainer"] {
            background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0f172a 100%) !important;
        }
        /* Center the form */
        .stForm {
            max-width: 360px !important;
            margin: 0 auto !important;
        }
        .stForm [data-testid="stFormSubmitButton"] button {
            background: linear-gradient(135deg, #1e3a5f, #2563eb) !important;
            color: white !important; border: none !important;
            padding: 12px !important; font-size: 16px !important;
            border-radius: 8px !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # Spacer + branding + form all in one flow
    st.markdown('<div style="height:12vh"></div>', unsafe_allow_html=True)

    st.markdown("""
    <div style="text-align:center;margin-bottom:24px">
        <div style="font-size:52px">🛡️</div>
        <h1 style="color:white;margin:8px 0 4px;font-size:26px">CityBCPAgent</h1>
        <p style="color:#94a3b8;font-size:14px;margin:0">Business Continuity Planning Dashboard</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Enter username", label_visibility="collapsed")
        password = st.text_input("Password", type="password", placeholder="Enter password", label_visibility="collapsed")
        submitted = st.form_submit_button("Login", use_container_width=True)

        if submitted:
            user = authenticate(username, password)
            if user:
                st.session_state["user"] = user
                token = _create_session_token(user["id"])
                st.query_params["session"] = token
                with get_db() as conn:
                    conn.execute("UPDATE users SET last_login = datetime('now') WHERE id = ?",
                                 (user["id"],))
                st.rerun()
            else:
                st.error("Invalid username or password")

    st.markdown('<p style="text-align:center;color:#475569;font-size:11px">Default: admin / admin123</p>',
                unsafe_allow_html=True)


def authenticate(username, password):
    """Authenticate user. Returns user dict or None."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? AND is_active = 1",
            (username,)
        ).fetchone()

    if row and verify_password(password, row["password_hash"]):
        return {
            "id": row["id"],
            "username": row["username"],
            "display_name": row["display_name"],
            "email": row["email"],
            "role": row["role"],
            "sectors": row["sectors"],
        }
    return None


# ─── User Management (Super Admin) ──────────────────────────────────────────

def create_user(username, password, display_name, email, role, sectors=None, created_by=None):
    """Create a new user. Returns (success, error_message)."""
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            return False, f"Username '{username}' already exists"

        conn.execute("""
            INSERT INTO users (username, password_hash, display_name, email, role, sectors, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (username, hash_password(password), display_name, email, role,
              ",".join(sectors) if sectors else None, created_by))
    return True, None


def list_users():
    """Get all users."""
    with get_db() as conn:
        import pandas as pd
        return pd.read_sql_query(
            "SELECT id, username, display_name, email, role, sectors, is_active, last_login, created_by, created_at FROM users ORDER BY role, username",
            conn
        )


def update_user(user_id, **kwargs):
    """Update user fields."""
    with get_db() as conn:
        for key, value in kwargs.items():
            if key == "password":
                conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                             (hash_password(value), user_id))
            elif key in ("display_name", "email", "role", "sectors", "is_active"):
                conn.execute(f"UPDATE users SET {key} = ? WHERE id = ?", (value, user_id))


def delete_user(user_id):
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


# ─── Sidebar User Info ──────────────────────────────────────────────────────

def render_sidebar_user():
    """Show dark sidebar style + user info + visible logout."""
    # Dark sidebar CSS (consistent across all pages)
    st.markdown("""
    <style>
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
        }
        [data-testid="stSidebar"] * { color: #e2e8f0 !important; }
        [data-testid="stSidebar"] .stButton button {
            background: rgba(255,255,255,0.1) !important;
            border: 1px solid rgba(255,255,255,0.2) !important;
            color: white !important;
            border-radius: 8px !important;
        }
        [data-testid="stSidebar"] .stButton button:hover {
            background: rgba(239,68,68,0.3) !important;
            border-color: #ef4444 !important;
        }
        .block-container { padding-top: 1rem !important; }
    </style>
    """, unsafe_allow_html=True)

    user = get_current_user()
    if not user:
        return

    role_info = ROLES.get(user["role"], {})
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"👤 **{user['display_name']}**")
    st.sidebar.caption(f"Role: {role_info.get('label', user['role'])}")
    if st.sidebar.button("🚪 Logout", key="btn_logout", use_container_width=True):
        logout()
        st.rerun()
