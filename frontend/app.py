import streamlit as st
import requests

st.set_page_config(page_title="InsightForge", layout="wide")

BACKEND_URL = "http://127.0.0.1:8001"

if "cleaning_log" not in st.session_state:
    st.session_state.cleaning_log = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False

# ---------------- Sidebar: Forge Assistant chatbot ----------------
with st.sidebar:
    st.header("🤖 Forge Assistant")
    st.caption("Synced to your current dataset — ask anything")

    for turn in st.session_state.chat_history:
        with st.chat_message(turn["role"]):
            st.write(turn["content"])

    user_msg = st.chat_input("Ask a question...")
    if user_msg:
        st.session_state.chat_history.append({"role": "user", "content": user_msg})
        with st.spinner("Forge Assistant is thinking..."):
            try:
                chat_response = requests.post(
                    f"{BACKEND_URL}/chat",
                    json={"message": user_msg, "history": st.session_state.chat_history[:-1]},
                    timeout=30
                )
                if chat_response.status_code == 200:
                    reply = chat_response.json()["reply"]
                else:
                    reply = "Sorry, something went wrong on the backend. Try again."
            except requests.exceptions.RequestException:
                reply = "Couldn't reach the backend — make sure the server is running."
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
        st.rerun()

# ---------------- Main area ----------------
st.title("InsightForge")
st.caption("AI-Guided Data Cleaning, Analysis, and Visualization")

uploaded_file = st.file_uploader("Upload a CSV file", type=["csv"], key="file_uploader")

if uploaded_file is not None:
    if "uploaded_filename" not in st.session_state or st.session_state.uploaded_filename != uploaded_file.name:
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "text/csv")}
        response = requests.post(f"{BACKEND_URL}/upload", files=files)

        if response.status_code == 200:
            st.session_state.uploaded_filename = uploaded_file.name
            st.session_state.profile = response.json()["profile"]
            st.session_state.rule_suggestions = response.json()["suggestions"]
            st.session_state.ai_suggestions = []
            st.session_state.cleaning_log = []
            st.session_state.chat_history = []
            st.session_state.data_loaded = True  # <- key fix: this flag, not uploaded_file, drives the UI

# Everything below now depends on data_loaded, not the raw uploader value —
# this survives reruns triggered by the sidebar chat instead of going blank.
if st.session_state.data_loaded:
    st.success(f"Active dataset: {st.session_state.uploaded_filename}")

    st.subheader("Dataset Overview")
    profile = st.session_state.profile
    st.write(f"Rows: {profile['row_count']}")
    st.write(f"Columns: {profile['column_count']}")
    st.write(f"Duplicate rows: {profile['duplicate_rows']}")

    download_response = requests.get(f"{BACKEND_URL}/download")
    if download_response.status_code == 200:
        st.download_button(
            "⬇ Download Current CSV",
            data=download_response.content,
            file_name="cleaned_data.csv",
            mime="text/csv"
        )

    def apply_and_sync(suggestion):
        apply_response = requests.post(f"{BACKEND_URL}/apply-suggestion", json=suggestion)
        if apply_response.status_code == 200:
            result = apply_response.json()
            st.session_state.profile = result["profile"]
            st.session_state.rule_suggestions = result["remaining_suggestions"]
            fixed_column = suggestion.get("column")
            st.session_state.ai_suggestions = [
                s for s in st.session_state.ai_suggestions if s.get("column") != fixed_column
            ]
            st.session_state.cleaning_log = result["cleaning_log"]
            st.rerun()

    st.subheader("Suggestions (Rule-Based)")
    if st.session_state.rule_suggestions:
        for i, s in enumerate(st.session_state.rule_suggestions):
            col1, col2 = st.columns([4, 1])
            col1.write(f"• {s['message']}")

            if s.get("issue") == "outliers":
                if col1.button("👀 View flagged values", key=f"view_{i}"):
                    ov = requests.get(f"{BACKEND_URL}/outlier-values", params={"column": s["column"]})
                    if ov.status_code == 200:
                        result = ov.json()
                        if "outlier_rows" in result:
                            st.dataframe(result["outlier_rows"])
                        else:
                            st.error(f"Backend says: {result.get('error', 'unknown error')}")
                    else:
                        st.error(f"Request failed with status {ov.status_code}")
                if col2.button("Cap anyway", key=f"cap_{i}"):
                    apply_and_sync({**s, "action": "cap_outliers"})
            else:
                if col2.button("Apply", key=f"rule_{i}"):
                    apply_and_sync(s)
    else:
        st.write("No issues detected.")

    if st.button("Get AI Suggestions"):
        with st.spinner("Asking Forge Assistant..."):
            ai_response = requests.post(f"{BACKEND_URL}/ai-suggest")
        if ai_response.status_code == 200:
            st.session_state.ai_suggestions = ai_response.json()["ai_suggestions"]

    if st.session_state.get("ai_suggestions"):
        st.subheader("Suggestions (AI-Powered)")
        for i, s in enumerate(st.session_state.ai_suggestions):
            col1, col2 = st.columns([4, 1])
            col1.write(f"🤖 {s['message']}")
            if col2.button("Apply", key=f"ai_{i}"):
                apply_and_sync(s)

    st.subheader("Cleaning Log")
    if st.session_state.cleaning_log:
        for entry in st.session_state.cleaning_log:
            st.write(f"🕒 {entry['timestamp']} — {entry['message']}")
    else:
        st.write("No actions applied yet.")
else:
    st.info("Upload a CSV file above to get started.")