"""
frontend/login_view.py : Streamlit login / sign-up screen.

Usage in frontend/app.py (put near the top, right after st.set_page_config):

    from frontend.login_view import require_login, auth_headers, logout_button
    require_login(API_URL)      # shows the login page and stops the app until logged in
    logout_button()             # optional: put in the sidebar

When calling the backend later, pass the token:
    requests.post(f"{API_URL}/upload", files=..., headers=auth_headers())
"""
import requests
import streamlit as st


def auth_headers() -> dict:
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def logout_button():
    if st.sidebar.button("Log out"):
        st.session_state.pop("token", None)
        st.session_state.pop("user_email", None)
        st.rerun()


def _error_text(resp: requests.Response) -> str:
    try:
        detail = resp.json().get("detail", "Something went wrong")
        if isinstance(detail, list):  # pydantic validation errors
            return "Check your details: email needs @, password needs 8+ characters."
        return str(detail)
    except Exception:
        return "Something went wrong"


def require_login(api_url: str):
    """Call at the top of app.py. Returns only if the user is logged in."""
    if st.session_state.get("token"):
        return

    st.title("InsightForge")
    st.caption("Log in to clean, explore and chart your data.")

    login_tab, signup_tab = st.tabs(["Log in", "Create account"])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in")
        if submitted:
            try:
                r = requests.post(f"{api_url}/auth/login", json={"email": email, "password": password}, timeout=30)
            except requests.RequestException:
                st.error("Can't reach the server. Try again in a moment.")
            else:
                if r.ok:
                    st.session_state["token"] = r.json()["access_token"]
                    st.session_state["user_email"] = r.json()["email"]
                    st.rerun()
                else:
                    st.error(_error_text(r))

    with signup_tab:
        with st.form("signup_form"):
            email = st.text_input("Email", key="su_email")
            password = st.text_input("Password (8+ characters)", type="password", key="su_pw")
            confirm = st.text_input("Confirm password", type="password", key="su_pw2")
            submitted = st.form_submit_button("Create account")
        if submitted:
            if password != confirm:
                st.error("Passwords don't match.")
            else:
                try:
                    r = requests.post(f"{api_url}/auth/register", json={"email": email, "password": password}, timeout=30)
                except requests.RequestException:
                    st.error("Can't reach the server. Try again in a moment.")
                else:
                    if r.ok:
                        st.success("Account created. Switch to the Log in tab.")
                    else:
                        st.error(_error_text(r))

    st.stop()