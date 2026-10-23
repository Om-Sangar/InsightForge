import html
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="InsightForge", page_icon="📊", layout="wide")

BACKEND_URL = "http://127.0.0.1:8001"

PAGES = ["Upload Data", "Data Cleaning", "Table Creation", "Dashboard"]
PAGE_ICONS = {
    "Upload Data": "📁",
    "Data Cleaning": "🧹",
    "Table Creation": "📊",
    "Dashboard": "📈",
}
INFORMATIONAL_ISSUES = {"outliers", "future_dates", "invalid_emails"}

# ---------------- Session defaults ----------------
DEFAULTS = {
    "page": PAGES[0],
    "data_loaded": False,
    "uploaded_filename": None,
    "upload_sig": None,
    "profile": {},
    "rule_suggestions": [],
    "ai_suggestions": [],
    "cleaning_log": [],
    "chat_history": [],
    "chat_open": False,
    "table_suggestions": [],
    "created_tables": [],
    "flash": [],
    "editing_key": None,
}
for _key, _value in DEFAULTS.items():
    if _key not in st.session_state:
        st.session_state[_key] = _value

# A hot-reload can leave an old page name in the session; reset it safely
if st.session_state.page not in PAGES:
    st.session_state.page = PAGES[0]

# ---------------- Aurora theme (purple + teal) ----------------
THEME_CSS = """
<style>
.stApp { background: #F6F3FB; }
div[data-testid="stMainBlockContainer"], .block-container { padding-top: 2rem; max-width: 1500px; }
header[data-testid="stHeader"] { background: transparent; }
footer, .stAppDeployButton, [data-testid="stDeployButton"] { display: none !important; }

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div:first-child {
    background: linear-gradient(180deg, #5B2E91 0%, #1F7A8C 100%) !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button,
section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] svg { color: #FFFFFF; }

.brand { display: flex; align-items: center; gap: .8rem; padding: .4rem .2rem 1.2rem .2rem; }
.brand-logo { width: 42px; height: 42px; border-radius: 50%; background: #FFFFFF; display: flex;
    align-items: flex-end; justify-content: center; gap: 3px; padding-bottom: 11px; box-sizing: border-box; }
.brand-logo i { display: block; width: 5px; border-radius: 2px; background: #5B2E91; }
.brand-logo i:nth-child(1) { height: 10px; }
.brand-logo i:nth-child(2) { height: 18px; }
.brand-logo i:nth-child(3) { height: 13px; }
.brand-name { color: #FFFFFF; font-size: 1.35rem; font-weight: 800; line-height: 1.1; }
.brand-tag { color: #C9B6E6; font-size: .78rem; }
.side-label { color: #C9B6E6; font-size: .72rem; letter-spacing: .16em; font-weight: 700; margin: .4rem 0 .5rem .3rem; }

div[class*="st-key-nav_"] { width: 100% !important; }
.st-key-nav_box .stButton button {
    width: 100%; justify-content: flex-start; background: transparent; border: none;
    border-radius: 12px; padding: .72rem 1rem; box-shadow: none; transition: background .15s;
}
.st-key-nav_box .stButton button p { color: #F1E9FB; font-size: 1rem; font-weight: 500; text-align: left; }
.st-key-nav_box .stButton button:hover { background: rgba(255,255,255,.16); border: none; }
.st-key-nav_box .stButton button:hover p { color: #FFFFFF; }
.st-key-nav_box .stButton button:focus:not(:active) { border: none; box-shadow: none; }

.dataset-card { background: rgba(255,255,255,.14); border-radius: 14px; padding: .9rem 1rem; margin-top: 1.4rem; }
.dataset-card .side-label { margin: 0 0 .35rem 0; }
.ds-name { color: #FFFFFF; font-weight: 700; font-size: .98rem; word-break: break-all; }
.ds-meta { color: #F1E9FB; font-size: .82rem; margin-top: .15rem; }

/* ---------- Page header banner ---------- */
.page-hero { background: linear-gradient(120deg, #5B2E91 0%, #8B3FD9 45%, #2BB3A3 100%);
    border-radius: 20px; padding: 1.4rem 1.8rem; margin-bottom: 1.2rem; }
.page-hero h1 { color: #FFFFFF; font-size: 1.8rem; margin: 0; padding: 0; }
.page-hero p { color: rgba(255,255,255,.9); margin: .3rem 0 0 0; }

/* ---------- Cards, buttons ---------- */
div[data-testid="stMetric"] { background: #FFFFFF; border: 1px solid #E6DEF3; border-left: 6px solid #8B3FD9;
    border-radius: 16px; padding: 14px 18px; }
div[data-testid="stMetricLabel"] p { color: #7A6C94; }
div[data-testid="stMetricValue"] { color: #2A1745; font-weight: 700; }

.stButton button, .stDownloadButton button { border-radius: 999px; border: 1px solid #D8C9F0; font-weight: 600; transition: all .15s; }
.stButton button:hover, .stDownloadButton button:hover { border-color: #8B3FD9; color: #8B3FD9; }
.stButton button[kind="primary"], .stDownloadButton button[kind="primary"] {
    background: linear-gradient(120deg, #8B3FD9, #2BB3A3); color: #FFFFFF; border: none; }
.stButton button[kind="primary"]:hover { color: #FFFFFF; filter: brightness(1.06); }

/* ---------- Forge Assistant: floating button + slide-in panel ---------- */
.st-key-assistant_fab { position: fixed; right: 28px; bottom: 28px; z-index: 1000000; width: auto !important; }
.st-key-assistant_fab .stButton button {
    background: linear-gradient(120deg, #8B3FD9, #2BB3A3); color: #FFFFFF; border: none;
    padding: .8rem 1.5rem; box-shadow: 0 12px 30px rgba(91,46,145,.38);
}
.st-key-assistant_fab .stButton button p { color: #FFFFFF; font-weight: 700; font-size: 1rem; }
.st-key-assistant_fab .stButton button:hover { filter: brightness(1.08); color: #FFFFFF; }

.st-key-chat_panel {
    position: fixed; top: 0; right: 0; width: 410px; height: 100vh; z-index: 1000001;
    background: #FFFFFF; border-left: 1px solid #E6DEF3; box-shadow: -10px 0 36px rgba(42,23,69,.16);
    padding: 1.1rem 1.25rem 1rem 1.25rem; overflow-y: auto; animation: slideInRight .28s ease-out;
}
@keyframes slideInRight { from { transform: translateX(100%); opacity: .6; } to { transform: translateX(0); opacity: 1; } }
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)


# ---------------- Small helpers ----------------
def go_to(page: str):
    st.session_state.page = page


def open_chat():
    st.session_state.chat_open = True


def close_chat():
    st.session_state.chat_open = False


def clear_derived_tables():
    st.session_state.table_suggestions = []
    st.session_state.created_tables = []


def clear_created_tables():
    st.session_state.created_tables = []


def toggle_editor(edit_key: str):
    st.session_state.editing_key = None if st.session_state.editing_key == edit_key else edit_key


def require_data() -> bool:
    if st.session_state.data_loaded:
        return True
    st.info("Upload a CSV file first to use this step.")
    st.button("Go to Upload →", on_click=go_to, args=(PAGES[0],))
    return False


def page_header(page: str, subtitle: str):
    st.markdown(
        f'<div class="page-hero"><h1>{PAGE_ICONS[page]} {page}</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


def inject_dynamic_css():
    """Highlights the active nav item and makes room for the assistant panel when it's open."""
    active_idx = PAGES.index(st.session_state.page)
    css = f"""
    .st-key-nav_{active_idx} .stButton button {{
        background: #FFFFFF !important; box-shadow: 0 6px 18px rgba(0,0,0,.2) !important;
    }}
    .st-key-nav_{active_idx} .stButton button p {{ color: #5B2E91 !important; font-weight: 700 !important; }}
    """
    if st.session_state.chat_open:
        css += """
        div[data-testid="stMainBlockContainer"], .block-container { padding-right: 440px !important; }
        """
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# ---------------- Left navigation ----------------
def step_done(page: str) -> bool:
    s = st.session_state
    if page == "Upload Data":
        return s.data_loaded
    if page == "Data Cleaning":
        return s.data_loaded and len(s.cleaning_log) > 0
    if page == "Table Creation":
        return len(s.created_tables) > 0
    return False


def nav_label(page: str) -> str:
    tick = "   ✓" if step_done(page) else ""
    return f"{PAGE_ICONS[page]}  {page}{tick}"


def render_sidebar():
    with st.sidebar:
        st.markdown(
            '<div class="brand"><div class="brand-logo"><i></i><i></i><i></i></div>'
            '<div><div class="brand-name">InsightForge</div>'
            '<div class="brand-tag">AI-guided data analytics</div></div></div>'
            '<div class="side-label">WORKFLOW</div>',
            unsafe_allow_html=True,
        )
        with st.container(key="nav_box"):
            for i, page in enumerate(PAGES):
                st.button(nav_label(page), key=f"nav_{i}", on_click=go_to, args=(page,))

        if st.session_state.data_loaded:
            p = st.session_state.profile
            name = html.escape(str(st.session_state.uploaded_filename))
            st.markdown(
                f'<div class="dataset-card"><div class="side-label">ACTIVE DATASET</div>'
                f'<div class="ds-name">{name}</div>'
                f'<div class="ds-meta">{p["row_count"]} rows · {p["column_count"]} columns</div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="dataset-card"><div class="side-label">ACTIVE DATASET</div>'
                '<div class="ds-meta">No dataset loaded yet</div></div>',
                unsafe_allow_html=True,
            )


# ---------------- Forge Assistant (opens from the right on demand) ----------------
def ask_assistant(message: str) -> str:
    try:
        r = requests.post(
            f"{BACKEND_URL}/chat",
            json={"message": message, "history": st.session_state.chat_history[:-1]},
            timeout=30,
        )
        return r.json()["reply"] if r.status_code == 200 else "Something went wrong on the backend."
    except requests.exceptions.RequestException:
        return "Couldn't reach the backend — make sure the server is running."


def render_chat_fab():
    with st.container(key="assistant_fab"):
        st.button("🤖  Forge Assistant", key="open_chat", on_click=open_chat)


def render_chat_panel():
    with st.container(key="chat_panel"):
        h1, h2 = st.columns([4, 1])
        h1.markdown("#### 🤖 Forge Assistant")
        h2.button("✕", key="close_chat", on_click=close_chat)
        st.caption("Synced to your current dataset")

        history_box = st.container(height=450)
        with history_box:
            if not st.session_state.chat_history:
                st.caption("Ask anything about your data, e.g. “What's wrong with this dataset?”")
            for turn in st.session_state.chat_history:
                with st.chat_message(turn["role"]):
                    st.write(turn["content"])

        user_msg = st.chat_input("Ask a question...", key="chat_box")
        if user_msg:
            st.session_state.chat_history.append({"role": "user", "content": user_msg})
            with history_box:
                with st.chat_message("user"):
                    st.write(user_msg)
                with st.spinner("Forge Assistant is thinking..."):
                    reply = ask_assistant(user_msg)
            st.session_state.chat_history.append({"role": "assistant", "content": reply})
            st.rerun()


# ---------------- Screen 1: Upload ----------------
def page_upload():
    page_header("Upload Data", "Upload a CSV file. Placeholder values like N/A, null and '-' are treated as missing automatically.")

    uploaded_file = st.file_uploader("Upload a CSV file", type=["csv"], key="file_uploader")

    if uploaded_file is not None:
        sig = f"{uploaded_file.name}:{uploaded_file.size}"
        if st.session_state.upload_sig != sig:
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "text/csv")}
            try:
                response = requests.post(f"{BACKEND_URL}/upload", files=files, timeout=60)
            except requests.exceptions.RequestException:
                st.error("Couldn't reach the backend — make sure the server is running.")
                return
            if response.status_code != 200:
                st.error(f"Upload failed (status {response.status_code}).")
                return

            data = response.json()
            st.session_state.upload_sig = sig
            st.session_state.uploaded_filename = uploaded_file.name
            st.session_state.profile = data["profile"]
            st.session_state.rule_suggestions = data["suggestions"]
            st.session_state.ai_suggestions = []
            st.session_state.cleaning_log = []
            st.session_state.chat_history = []
            st.session_state.flash = []
            st.session_state.editing_key = None
            clear_derived_tables()
            st.session_state.data_loaded = True
            st.rerun()

    if st.session_state.data_loaded:
        st.success(f"Active dataset: {st.session_state.uploaded_filename}")
        p = st.session_state.profile
        c1, c2, c3 = st.columns(3)
        c1.metric("Rows", p["row_count"])
        c2.metric("Columns", p["column_count"])
        c3.metric("Duplicate rows", p["duplicate_rows"])
        st.button("Continue to Data Cleaning →", type="primary", on_click=go_to, args=(PAGES[1],))


# ---------------- Screen 2: Data Cleaning ----------------
def apply_and_sync(suggestion: dict):
    r = requests.post(f"{BACKEND_URL}/apply-suggestion", json=suggestion)
    result = r.json() if r.status_code == 200 else {}
    if "profile" not in result:
        st.error("Could not apply that suggestion.")
        return

    st.session_state.profile = result["profile"]
    st.session_state.rule_suggestions = result["remaining_suggestions"]
    fixed_column = suggestion.get("column")
    st.session_state.ai_suggestions = [
        s for s in st.session_state.ai_suggestions if s.get("column") != fixed_column
    ]
    st.session_state.cleaning_log = result["cleaning_log"]
    clear_derived_tables()  # tables built from older data would now be stale
    st.rerun()


def render_correction_editor(s: dict, key_prefix: str, index: int):
    issue, column = s["issue"], s["column"]

    fv = requests.get(f"{BACKEND_URL}/flagged-values", params={"column": column, "kind": issue})
    rows = fv.json().get("flagged_rows", []) if fv.status_code == 200 else []
    if not rows:
        st.info("No flagged values left to correct.")
        return

    hint = (
        "Type a valid email, e.g. name@example.com."
        if issue == "invalid_emails"
        else "Type a valid date that is not in the future, e.g. 2024-05-10."
    )
    st.caption(f"Edit the '{column}' cells below. {hint}")

    original = pd.DataFrame(rows)
    ids_signature = abs(hash(tuple(original["_row_id"].tolist())))
    edited = st.data_editor(
        original,
        disabled=[c for c in original.columns if c != column],
        hide_index=True,
        key=f"editor_{issue}_{column}_{ids_signature}",
    )

    if st.button("💾 Save corrections", key=f"save_{key_prefix}_{index}", type="primary"):
        changes = []
        for i in range(len(original)):
            old = original.iloc[i][column]
            new = edited.iloc[i][column]
            if pd.notna(new) and str(new) != str(old):
                changes.append({"row_id": int(original.iloc[i]["_row_id"]), "value": str(new)})

        if not changes:
            st.info("No changes to save yet — edit a cell first.")
            return

        resp = requests.post(
            f"{BACKEND_URL}/update-values",
            json={"column": column, "kind": issue, "changes": changes},
        )
        result = resp.json() if resp.status_code == 200 else {}
        if "profile" not in result:
            st.error(result.get("error", "Could not save corrections."))
            return

        rejected = result.get("rejected", [])
        if result["updated"] == 0:
            for r in rejected:
                st.warning(f"Row {r['row_id']}: “{r['value']}” not saved — {r['reason']}.")
            return

        st.session_state.profile = result["profile"]
        st.session_state.rule_suggestions = result["remaining_suggestions"]
        st.session_state.ai_suggestions = [
            x for x in st.session_state.ai_suggestions if x.get("column") != column
        ]
        st.session_state.cleaning_log = result["cleaning_log"]
        clear_derived_tables()
        st.session_state.editing_key = None

        messages = [("success", f"Corrected {result['updated']} value(s) in '{column}'.")]
        for r in rejected:
            messages.append(("warning", f"Row {r['row_id']}: “{r['value']}” not saved — {r['reason']}."))
        st.session_state.flash = messages
        st.rerun()


def render_suggestion_row(s: dict, key_prefix: str, index: int):
    col1, col2 = st.columns([4, 1])
    col1.write(f"• {s['message']}")
    issue = s.get("issue")

    if issue in INFORMATIONAL_ISSUES:
        if col1.button("👀 View flagged values", key=f"{key_prefix}_view_{index}"):
            fv = requests.get(
                f"{BACKEND_URL}/flagged-values",
                params={"column": s["column"], "kind": issue},
            )
            if fv.status_code == 200 and "flagged_rows" in fv.json():
                st.dataframe(fv.json()["flagged_rows"])
            else:
                st.error("Could not load flagged values.")

        if issue == "outliers":
            if col2.button("Cap anyway", key=f"{key_prefix}_cap_{index}"):
                apply_and_sync({**s, "action": "cap_outliers"})

        else:  # invalid_emails or future_dates
            blank_action = "blank_invalid_emails" if issue == "invalid_emails" else "blank_future_dates"
            drop_action = "drop_invalid_emails" if issue == "invalid_emails" else "drop_future_dates"
            edit_key = f"{issue}:{s['column']}"

            b1, b2, b3 = st.columns(3)
            b1.button(
                "✏️ Correct manually",
                key=f"{key_prefix}_edit_{index}",
                on_click=toggle_editor,
                args=(edit_key,),
            )
            if b2.button("Blank (mark missing)", key=f"{key_prefix}_blank_{index}"):
                apply_and_sync({**s, "action": blank_action})
            if b3.button("Drop those rows", key=f"{key_prefix}_drop_{index}"):
                apply_and_sync({**s, "action": drop_action})

            if st.session_state.editing_key == edit_key:
                render_correction_editor(s, key_prefix, index)
    else:
        if col2.button("Apply", key=f"{key_prefix}_{index}"):
            apply_and_sync(s)


def page_cleaning():
    page_header("Data Cleaning", "Review detected issues, apply fixes, and track every change in the audit log.")
    if not require_data():
        return

    for level, text in st.session_state.flash:
        getattr(st, level)(text)
    st.session_state.flash = []

    p = st.session_state.profile
    m1, m2, m3, m4 = st.columns([1, 1, 1, 1.3])
    m1.metric("Rows", p["row_count"])
    m2.metric("Columns", p["column_count"])
    m3.metric("Duplicate rows", p["duplicate_rows"])
    if m4.button("↺ Reset to Original"):
        reset = requests.post(f"{BACKEND_URL}/reset")
        result = reset.json() if reset.status_code == 200 else {}
        if "profile" in result:
            st.session_state.profile = result["profile"]
            st.session_state.rule_suggestions = result["suggestions"]
            st.session_state.ai_suggestions = []
            st.session_state.cleaning_log = result["cleaning_log"]
            st.session_state.editing_key = None
            clear_derived_tables()
            st.rerun()
        else:
            st.error("Could not reset the dataset.")

    with st.expander("📊 Compare Original vs Current"):
        cmp_resp = requests.get(f"{BACKEND_URL}/compare")
        if cmp_resp.status_code == 200 and "original" in cmp_resp.json():
            cmp = cmp_resp.json()
            c1, c2 = st.columns(2)
            c1.write("**Original**")
            c1.write(f"Rows: {cmp['original']['row_count']}")
            c1.write(f"Duplicate rows: {cmp['original']['duplicate_rows']}")
            c2.write("**Current**")
            c2.write(f"Rows: {cmp['current']['row_count']}")
            c2.write(f"Duplicate rows: {cmp['current']['duplicate_rows']}")

    dl = requests.get(f"{BACKEND_URL}/download")
    if dl.status_code == 200:
        st.download_button(
            "⬇ Download Current CSV",
            data=dl.content,
            file_name="cleaned_data.csv",
            mime="text/csv",
        )

    with st.container(border=True):
        st.subheader("Suggestions (Rule-Based)")
        if st.session_state.rule_suggestions:
            for i, s in enumerate(st.session_state.rule_suggestions):
                render_suggestion_row(s, "rule", i)
        else:
            st.write("No issues detected.")

    if st.button("✨ Get AI Suggestions"):
        with st.spinner("Asking Forge Assistant..."):
            ai = requests.post(f"{BACKEND_URL}/ai-suggest")
        if ai.status_code == 200 and "ai_suggestions" in ai.json():
            st.session_state.ai_suggestions = ai.json()["ai_suggestions"]
        else:
            st.error("Could not get AI suggestions.")

    if st.session_state.ai_suggestions:
        with st.container(border=True):
            st.subheader("Suggestions (AI-Powered)")
            for i, s in enumerate(st.session_state.ai_suggestions):
                render_suggestion_row(s, "ai", i)

    with st.container(border=True):
        st.subheader("Cleaning Log")
        if st.session_state.cleaning_log:
            for entry in st.session_state.cleaning_log:
                st.write(f"🕒 {entry['timestamp']} — {entry['message']}")
        else:
            st.write("No actions applied yet.")

    st.button("Continue to Table Creation →", type="primary", on_click=go_to, args=(PAGES[2],))


# ---------------- Screen 3: Table Creation ----------------

def create_table_from(t: dict):
    resp = requests.post(f"{BACKEND_URL}/create-table", json=t)
    result = resp.json() if resp.status_code == 200 else {}
    if "rows" in result:
        already = any(x["title"] == result["title"] for x in st.session_state.created_tables)
        if not already:
            st.session_state.created_tables.append(result)
        st.rerun()
    else:
        st.error(result.get("error", f"Request failed with status {resp.status_code}"))


def page_tables():
    from ai_picks_view import fetch_picks, get_picks, show_ai_fallback_notice

    page_header("Table Creation", "Summarize your cleaned data into useful groupings.")
    if not require_data():
        return

    pending = [
        s for s in st.session_state.rule_suggestions
        if s.get("issue") not in INFORMATIONAL_ISSUES
    ]
    if pending:
        st.warning(
            f"{len(pending)} cleaning suggestion(s) are still open — "
            "tables are most accurate after cleaning."
        )
        st.button("← Back to Data Cleaning", on_click=go_to, args=(PAGES[1],))

    b1, b2, _spacer = st.columns([1, 1, 3])
    if b1.button("✨ AI picks", type="primary"):
        with st.spinner("Forge Assistant is choosing the most useful tables..."):
            fetch_picks(BACKEND_URL, "tables")
    if b2.button("Suggest Tables"):
        with st.spinner("Analyzing columns..."):
            ts = requests.get(f"{BACKEND_URL}/table-suggestions")
        if ts.status_code == 200:
            st.session_state.table_suggestions = ts.json().get("table_suggestions", [])
        else:
            st.error("Could not get table suggestions.")

    ai = get_picks("tables")
    if ai:
        with st.container(border=True):
            st.subheader("✨ Forge Assistant's picks")
            show_ai_fallback_notice(ai)
            for i, t in enumerate(ai["picks"]):
                col1, col2 = st.columns([4, 1])
                col1.write(f"**{t['title']}**")
                col1.caption(t["reason"])
                if col2.button("Create", key=f"ai_table_{i}"):
                    create_table_from(t)
    elif st.session_state.get("ai_tables_picks"):
        st.caption("Your data changed since the last AI picks — click “✨ AI picks” to refresh them.")

    if st.session_state.table_suggestions:
        with st.container(border=True):
            st.subheader("All suggestions")
            for i, t in enumerate(st.session_state.table_suggestions):
                col1, col2 = st.columns([4, 1])
                col1.write(f"• **{t['title']}** — {t['rationale']}")
                if col2.button("Create", key=f"table_{i}"):
                    create_table_from(t)

    for table in st.session_state.created_tables:
        with st.container(border=True):
            st.subheader(table["title"])
            st.dataframe(table["rows"])
    if st.session_state.created_tables:
        st.button("Clear tables", on_click=clear_created_tables)

    st.button("Continue to Dashboard →", type="primary", on_click=go_to, args=(PAGES[3],))


# ---------------- Screen 4: Dashboard ----------------
def page_dashboard():
    page_header("Dashboard", "Turn your cleaned data into charts and KPIs.")
    if not require_data():
        return
    from dashboard_view import render_dashboard
    render_dashboard(BACKEND_URL)


# ---------------- Router ----------------
PAGE_FUNCS = {
    "Upload Data": page_upload,
    "Data Cleaning": page_cleaning,
    "Table Creation": page_tables,
    "Dashboard": page_dashboard,
}

inject_dynamic_css()
render_sidebar()
PAGE_FUNCS[st.session_state.page]()

if st.session_state.chat_open:
    render_chat_panel()
else:
    render_chat_fab()