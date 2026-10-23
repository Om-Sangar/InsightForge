import requests
import streamlit as st


def data_sig() -> str:
    """Changes whenever the dataset changes (new upload or any cleaning action)."""
    s = st.session_state
    return f"{s.get('upload_sig')}:{len(s.get('cleaning_log', []))}"


def fetch_picks(backend_url: str, kind: str) -> None:
    try:
        resp = requests.get(f"{backend_url}/ai-picks", params={"kind": kind})
        result = resp.json() if resp.status_code == 200 else {}
    except requests.exceptions.RequestException:
        st.error("Couldn't reach the backend — make sure the server is running.")
        return

    if "picks" not in result:
        st.error(result.get("error", "Could not get AI picks."))
        return

    st.session_state[f"ai_{kind}_picks"] = {
        "sig": data_sig(),
        "picks": result["picks"],
        "ai": result.get("ai", True),
        "ai_error": result.get("ai_error"),
    }


def get_picks(kind: str):
    """Returns saved picks only if the data hasn't changed since they were made."""
    stored = st.session_state.get(f"ai_{kind}_picks")
    if stored and stored["sig"] == data_sig():
        return stored
    return None


def show_ai_fallback_notice(stored: dict) -> None:
    if not stored.get("ai", True):
        reason = stored.get("ai_error") or "unknown reason"
        st.warning(
            "AI is unavailable right now — showing the top rule-based suggestions instead.\n\n"
            f"**Reason:** {reason}"
        )