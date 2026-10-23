import pandas as pd
import plotly.express as px
import requests
import streamlit as st

from ai_picks_view import data_sig, fetch_picks, get_picks, show_ai_fallback_notice

# Aurora palette: purple + teal
PALETTE = ["#8B3FD9", "#2BB3A3", "#B565E6", "#4FD1C5", "#5B2E91", "#F59E0B", "#7C3AED", "#14B8A6"]
PURPLE, TEAL = PALETTE[0], PALETTE[1]

# Widths are in twelfths of the row, so 4 = a third, 6 = half, 8 = two thirds, 12 = full
WIDTHS = {"Small (⅓)": 4, "Medium (½)": 6, "Large (⅔)": 8, "Full width": 12}
WIDTH_LABELS = list(WIDTHS)
STYLES = ["Auto", "Bar", "Horizontal bar", "Donut"]
CATEGORY_TYPES = ("bar", "donut")


# ---------------- Formatting + figures ----------------
def _nice(name) -> str:
    return str(name).replace("_", " ").title()


def _fmt_kpi(kpi: dict) -> str:
    value = kpi["value"]
    if kpi["kind"] == "count":
        return f"{int(value):,}"
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    return f"{value:,.2f}"


def _style(fig, height: int = 340):
    is_pie = len(fig.data) > 0 and fig.data[0].type == "pie"
    is_horizontal = len(fig.data) > 0 and getattr(fig.data[0], "orientation", None) == "h"

    if is_pie:
        # Legend sits to the right of the donut so it can never overlap the ring
        margin = dict(l=10, r=110, t=10, b=10)
        legend = dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02)
    else:
        margin = dict(l=60, r=20, t=10, b=60)
        legend = dict(orientation="h", yanchor="top", y=-0.12, xanchor="center", x=0.5)

    fig.update_layout(
        height=height,
        margin=margin,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#2A1745"),
        colorway=PALETTE,
        legend=legend,
    )

    if not is_pie:
        # No axis titles: the card heading already says what the chart shows
        fig.update_xaxes(title=None, showgrid=False, linecolor="#E6DEF3", automargin=True)
        fig.update_yaxes(title=None, gridcolor="#EFE9F8", zeroline=False, automargin=True)
        if not is_horizontal:
            x_values = fig.data[0].x if len(fig.data) else None
            if x_values is not None and len(x_values) and max(len(str(v)) for v in x_values) > 9:
                fig.update_xaxes(tickangle=-30)
    return fig


def _make_figure(chart: dict, style: str = "Auto"):
    data = chart.get("data") or []
    if not data:
        return None

    df = pd.DataFrame(data)
    ctype = chart["type"]

    if ctype in CATEGORY_TYPES:
        # Bar and donut data are interchangeable, so the user can switch style freely
        if ctype == "donut":
            df = df.rename(columns={"label": "name"})
        else:
            df = df.rename(columns={"x": "name", "y": "value"})

        shape = {"Auto": ctype, "Bar": "bar", "Horizontal bar": "hbar", "Donut": "donut"}[style]

        if shape == "donut":
            df = df[df["value"] > 0]
            if df.empty:
                return None
            fig = px.pie(df, names="name", values="value", hole=0.55, color_discrete_sequence=PALETTE)
            fig.update_traces(textposition="inside", textinfo="percent")
        elif shape == "hbar":
            fig = px.bar(df.iloc[::-1], x="value", y="name", orientation="h")
            fig.update_traces(marker_color=PURPLE)
        else:
            fig = px.bar(df, x="name", y="value")
            fig.update_traces(marker_color=PURPLE)

    elif ctype == "line":
        fig = px.line(df, x="x", y="y", markers=True)
        fig.update_traces(line=dict(color=TEAL, width=3), marker=dict(size=7, color=TEAL))

    elif ctype == "histogram":
        fig = px.bar(df, x="bin", y="count")
        fig.update_traces(marker_color=PURPLE)
        fig.update_layout(bargap=0.06)

    else:
        return None

    return _style(fig)


# ---------------- Layout state (kept in session_state) ----------------
def _cfg() -> dict:
    return st.session_state.setdefault("dash_cfg", {})


def _label_for(width: int) -> str:
    for label, value in WIDTHS.items():
        if value == width:
            return label
    return "Medium (½)"


def sync_layout(specs: list):
    """Keeps the saved layout in step with the charts that currently exist."""
    cfg = _cfg()
    ids = [s["id"] for s in specs]
    old_order = list(st.session_state.get("dash_order", []))

    for s in specs:
        if s["id"] not in cfg:
            cfg[s["id"]] = {"vis": True, "width": 6, "style": "Auto", "type": s["type"]}

    st.session_state.dash_order = [c for c in old_order if c in ids] + [c for c in ids if c not in old_order]
    st.session_state.setdefault("dash_ver", 0)


def move_chart(cid: str, delta: int):
    cfg, order = _cfg(), st.session_state.dash_order
    visible = [c for c in order if cfg[c]["vis"]]
    if cid not in visible:
        return
    j = visible.index(cid) + delta
    if 0 <= j < len(visible):
        a, b = order.index(cid), order.index(visible[j])
        order[a], order[b] = order[b], order[a]


def hide_chart(cid: str):
    _cfg()[cid]["vis"] = False


def show_chart(cid: str):
    _cfg()[cid]["vis"] = True


def set_width(cid: str, widget_key: str):
    _cfg()[cid]["width"] = WIDTHS[st.session_state[widget_key]]


def set_style(cid: str, widget_key: str):
    _cfg()[cid]["style"] = st.session_state[widget_key]


def reset_layout(ids: list):
    cfg = _cfg()
    for cid in ids:
        if cid in cfg:
            cfg[cid].update({"vis": True, "width": 6, "style": "Auto"})
    st.session_state.dash_order = list(ids)
    st.session_state.dash_ver = st.session_state.get("dash_ver", 0) + 1


def bring_to_front(pick_ids: list):
    """Moves the AI's picks to the top row and gives them a matching width."""
    cfg = _cfg()
    order = st.session_state.dash_order
    front = [c for c in pick_ids if c in order]
    st.session_state.dash_order = front + [c for c in order if c not in front]
    pick_width = 4 if len(front) == 3 else 6
    for cid in front:
        cfg[cid]["vis"] = True
        cfg[cid]["width"] = pick_width
    st.session_state.dash_ver = st.session_state.get("dash_ver", 0) + 1


def pack_rows(ids: list) -> list:
    rows, current, used = [], [], 0
    cfg = _cfg()
    for cid in ids:
        width = cfg[cid]["width"]
        if current and used + width > 12:
            rows.append(current)
            current, used = [], 0
        current.append(cid)
        used += width
    if current:
        rows.append(current)
    return rows


# ---------------- Pieces of the screen ----------------
def render_chart_card(chart: dict, conf: dict, pos: int, total: int, arrange: bool, reason: str | None, ver: int):
    cid = chart["id"]
    is_category = chart["type"] in CATEGORY_TYPES

    with st.container(border=True):
        st.markdown(f"**{chart['title']}**" + (" ✨" if reason else ""))
        if reason:
            st.caption(reason)

        if arrange:
            b1, b2, b3, _gap = st.columns([1, 1, 1, 3])
            b1.button("◀", key=f"dash_left_{cid}", on_click=move_chart, args=(cid, -1),
                      disabled=pos == 0, help="Move earlier")
            b2.button("▶", key=f"dash_right_{cid}", on_click=move_chart, args=(cid, 1),
                      disabled=pos == total - 1, help="Move later")
            b3.button("✕", key=f"dash_hide_{cid}", on_click=hide_chart, args=(cid,), help="Hide this chart")

            w_col, s_col = st.columns(2)
            wkey = f"dash_w_{cid}_{ver}"
            w_col.selectbox(
                "Width", WIDTH_LABELS, index=WIDTH_LABELS.index(_label_for(conf["width"])),
                key=wkey, label_visibility="collapsed", on_change=set_width, args=(cid, wkey),
            )
            if is_category:
                skey = f"dash_s_{cid}_{ver}"
                s_col.selectbox(
                    "Style", STYLES, index=STYLES.index(conf["style"]),
                    key=skey, label_visibility="collapsed", on_change=set_style, args=(cid, skey),
                )
            else:
                s_col.caption("Style: fixed")

        fig = None if chart.get("error") else _make_figure(chart, conf["style"] if is_category else "Auto")
        if fig is None:
            st.caption("Not enough data for this chart with the current filters.")
        else:
            st.plotly_chart(fig, theme=None, key=f"dash_chart_{cid}", config={"displaylogo": False})


def render_data_summary(profile: dict, rows_after: int, total_rows: int):
    column_stats = profile.get("columns", {})
    missing_cells = sum(s.get("missing_count", 0) for s in column_stats.values())
    total_cells = profile.get("row_count", 0) * profile.get("column_count", 0)
    completeness = 100 * (1 - missing_cells / total_cells) if total_cells else 100.0
    n_actions = len(st.session_state.get("cleaning_log", []))

    with st.container(border=True):
        st.markdown("**📋 Data summary**")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Records shown", f"{rows_after:,}")
        m2.metric("Columns", f"{profile.get('column_count', 0):,}")
        m3.metric("Completeness", f"{completeness:.1f}%")
        m4.metric("Duplicate rows", f"{profile.get('duplicate_rows', 0):,}")
        m5.metric("Cleaning actions", f"{n_actions:,}")
        if rows_after != total_rows:
            st.caption(f"Filters are on: showing {rows_after:,} of {total_rows:,} records.")

        with st.expander("Column details"):
            rows = [
                {"Column": name, "Type": s["dtype"], "Missing %": s["missing_pct"], "Unique values": s["unique_values"]}
                for name, s in column_stats.items()
            ]
            st.dataframe(pd.DataFrame(rows), hide_index=True)


def build_summary_facts(kpis: list, charts: list, rows_after: int, total_rows: int, active_filters: dict) -> str:
    filter_note = f" (filtered by {', '.join(active_filters)})" if active_filters else ""
    lines = [f"Records: {rows_after} of {total_rows}{filter_note}"]
    for kpi in kpis:
        lines.append(f"{kpi['label']}: {_fmt_kpi(kpi)}")
    for chart in charts:
        data = chart.get("data") or []
        if chart["type"] == "bar" and len(data) >= 2:
            top, low = data[0], data[-1]  # the backend sorts bar data from highest to lowest
            lines.append(
                f"{chart['title']}: highest is {top['x']} ({top['y']:,.0f}), lowest is {low['x']} ({low['y']:,.0f})"
            )
    return "\n".join(lines[:12])


def request_ai_summary(backend_url: str, facts: str, sig: str):
    prompt = (
        "Write a plain-language summary of this dataset for a business owner in 3 to 4 sentences. "
        "Mention the most important numbers and one notable pattern. "
        "Use only the facts below and do not invent any numbers.\n\nFacts:\n" + facts
    )
    text = None
    try:
        r = requests.post(f"{backend_url}/chat", json={"message": prompt, "history": []}, timeout=40)
        text = r.json().get("reply") if r.status_code == 200 else None
    except requests.exceptions.RequestException:
        pass
    st.session_state.dash_ai_summary = {
        "sig": sig,
        "text": text or "Couldn't get a summary right now — please try again in a moment.",
    }


# ---------------- The dashboard screen ----------------
def render_dashboard(backend_url: str):
    try:
        sugg_resp = requests.get(f"{backend_url}/chart-suggestions")
    except requests.exceptions.RequestException:
        st.error("Couldn't reach the backend — make sure the server is running.")
        return

    suggestions = sugg_resp.json() if sugg_resp.status_code == 200 else {}
    specs = suggestions.get("chart_suggestions", [])
    filter_options = suggestions.get("filter_options", {})

    if not specs:
        st.info("This dataset needs at least one category column and one number column to build charts.")
        return

    sync_layout(specs)
    spec_ids = [s["id"] for s in specs]

    # ---------------- Header controls ----------------
    h1, h2, h3, h4 = st.columns([1.25, 1.1, 1.35, 1.1])
    if h1.button("✨ AI chart picks", type="primary"):
        with st.spinner("Forge Assistant is choosing the most useful charts..."):
            fetch_picks(backend_url, "charts")
        stored = get_picks("charts")
        if stored and stored.get("ai"):
            bring_to_front([p["id"] for p in stored["picks"]])
    want_summary = h2.button("✨ AI summary")
    arrange = h3.toggle("🧩 Arrange layout", key="dash_arrange")
    h4.button("↺ Reset layout", on_click=reset_layout, args=(spec_ids,))

    if arrange:
        st.info("Arrange mode: use ◀ ▶ to reorder, pick a width or style, or ✕ to hide a chart.")

    # ---------------- Filters ----------------
    active_filters = {}
    if filter_options:
        n_active = sum(1 for name in filter_options if st.session_state.get(f"dash_filter_{name}"))
        label = "🎛 Filters" + (f" — {n_active} active" if n_active else " — all records")
        with st.expander(label):
            cols = st.columns(min(len(filter_options), 3))
            for i, (col_name, options) in enumerate(filter_options.items()):
                key = f"dash_filter_{col_name}"
                # Drop any previously selected values that no longer exist (e.g. after cleaning)
                st.session_state[key] = [v for v in st.session_state.get(key, []) if v in options]
                chosen = cols[i % len(cols)].multiselect(_nice(col_name), options, key=key, placeholder="All")
                if chosen:
                    active_filters[col_name] = chosen

    # ---------------- Fetch KPIs + chart data ----------------
    try:
        resp = requests.post(
            f"{backend_url}/dashboard",
            json={"charts": specs, "filters": active_filters},
        )
    except requests.exceptions.RequestException:
        st.error("Couldn't reach the backend — make sure the server is running.")
        return

    result = resp.json() if resp.status_code == 200 else {}
    if "charts" not in result:
        st.error(result.get("error", "Could not build the dashboard."))
        return

    kpis = result["kpis"]
    rows_after = result["rows_after_filter"]
    profile = st.session_state.get("profile", {})
    total_rows = profile.get("row_count", rows_after)

    # ---------------- KPI strip ----------------
    for col, kpi in zip(st.columns(len(kpis)), kpis):
        col.metric(kpi["label"], _fmt_kpi(kpi))

    if rows_after == 0:
        st.warning("No records match these filters. Clear a filter to see charts again.")
        return

    # ---------------- Data summary + AI summary ----------------
    render_data_summary(profile, rows_after, total_rows)

    summary_sig = f"{data_sig()}|{sorted(active_filters.items())}"
    if want_summary:
        with st.spinner("Forge Assistant is writing the summary..."):
            facts = build_summary_facts(kpis, result["charts"], rows_after, total_rows, active_filters)
            request_ai_summary(backend_url, facts, summary_sig)

    summary = st.session_state.get("dash_ai_summary")
    if summary:
        with st.container(border=True):
            st.markdown("**✨ AI summary**")
            st.write(summary["text"])
            if summary["sig"] != summary_sig:
                st.caption("Your data or filters changed since this was written — click “✨ AI summary” to refresh it.")

    # ---------------- AI picks status ----------------
    ai = get_picks("charts")
    reasons = {}
    if ai and ai.get("ai"):
        reasons = {p["id"]: p["reason"] for p in ai["picks"]}
    elif ai:
        show_ai_fallback_notice(ai)
    elif st.session_state.get("ai_charts_picks"):
        st.caption("Your data changed since the last AI picks — click “✨ AI chart picks” to refresh them.")

    # ---------------- Charts grid ----------------
    st.markdown("#### 📊 Charts")
    cfg = _cfg()
    charts_by_id = {c["id"]: c for c in result["charts"]}
    order = [c for c in st.session_state.dash_order if c in charts_by_id]
    visible = [c for c in order if cfg[c]["vis"]]
    hidden = [c for c in order if not cfg[c]["vis"]]
    ver = st.session_state.get("dash_ver", 0)

    if not visible:
        st.info("All charts are hidden. Turn on “🧩 Arrange layout” to bring some back.")

    for row in pack_rows(visible):
        weights = [cfg[c]["width"] for c in row]
        leftover = 12 - sum(weights)
        cols = st.columns(weights + ([leftover] if leftover > 0 else []))
        for col, cid in zip(cols, row):
            with col:
                render_chart_card(
                    charts_by_id[cid], cfg[cid], visible.index(cid), len(visible),
                    arrange, reasons.get(cid), ver,
                )

    if hidden:
        if arrange:
            with st.expander(f"👁 Hidden charts ({len(hidden)})"):
                for cid in hidden:
                    st.button(
                        f"➕ Show “{charts_by_id[cid]['title']}”",
                        key=f"dash_show_{cid}", on_click=show_chart, args=(cid,),
                    )
        else:
            st.caption(f"{len(hidden)} chart(s) hidden. Turn on “🧩 Arrange layout” to bring them back.")

    # ---------------- Summary tables created in step 3 ----------------
    tables = st.session_state.get("created_tables", [])
    if tables:
        st.markdown("#### 🗂 Summary tables")
        for start in range(0, len(tables), 2):
            for col, table in zip(st.columns(2), tables[start:start + 2]):
                with col:
                    with st.container(border=True):
                        st.markdown(f"**{table['title']}**")
                        st.dataframe(pd.DataFrame(table["rows"]), hide_index=True)
    else:
        st.caption("Tip: create summary tables in step 3 and they will show up here too.")

    st.caption("Tip: hover over a chart and click the camera icon to download it as an image.")