import requests
import streamlit as st

st.set_page_config(page_title="AI Knowledge Base", page_icon="📚", layout="wide")

# ------------------------------------------------------------------ #
# Session state
# ------------------------------------------------------------------ #
if "token" not in st.session_state:
    st.session_state.token = None
if "email" not in st.session_state:
    st.session_state.email = None
if "selected_doc_id" not in st.session_state:
    st.session_state.selected_doc_id = None


def auth_headers() -> dict:
    return {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}


def api_url(base: str, path: str) -> str:
    return base.rstrip("/") + path


# ------------------------------------------------------------------ #
# Sidebar: API base URL + auth status
# ------------------------------------------------------------------ #
st.sidebar.title("📚 Knowledge Base")

base_url = "http://127.0.0.1:8000"

if st.session_state.token:
    st.sidebar.success(f"Logged in as **{st.session_state.email}**")
    if st.sidebar.button("Log out"):
        st.session_state.token = None
        st.session_state.email = None
        st.session_state.selected_doc_id = None
        st.rerun()
else:
    st.sidebar.info("Not logged in")


# ------------------------------------------------------------------ #
# Login / Register screen (shown until authenticated)
# ------------------------------------------------------------------ #
def render_auth_screen():
    st.title("Welcome to the AI Knowledge Base")
    st.caption("Register or log in to upload documents and ask questions about them.")

    login_tab, register_tab = st.tabs(["Log in", "Register"])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Log in", use_container_width=True)

        if submitted:
            try:
                resp = requests.post(
                    api_url(base_url, "/auth/login"),
                    json={"email": email, "password": password},
                    timeout=15,
                )
            except requests.RequestException as exc:
                st.error(f"Could not reach the API: {exc}")
            else:
                if resp.status_code == 200:
                    st.session_state.token = resp.json()["access_token"]
                    st.session_state.email = email
                    st.rerun()
                else:
                    st.error(resp.json().get("detail", "Login failed"))

    with register_tab:
        with st.form("register_form"):
            email = st.text_input("Email", key="register_email")
            password = st.text_input(
                "Password", type="password", key="register_password", help="At least 6 characters"
            )
            submitted = st.form_submit_button("Create account", use_container_width=True)

        if submitted:
            try:
                resp = requests.post(
                    api_url(base_url, "/auth/register"),
                    json={"email": email, "password": password},
                    timeout=15,
                )
            except requests.RequestException as exc:
                st.error(f"Could not reach the API: {exc}")
            else:
                if resp.status_code == 201:
                    st.success("Account created! Switch to the Log in tab to sign in.")
                else:
                    st.error(resp.json().get("detail", "Registration failed"))


# ------------------------------------------------------------------ #
# Main app (shown once authenticated)
# ------------------------------------------------------------------ #
def render_upload_tab():
    st.subheader("Add a document")
    file_tab, manual_tab = st.tabs(["⬆️ Upload a file", "⌨️ Type / paste text"])

    with file_tab:
        uploaded_file = st.file_uploader("PDF, DOCX, or TXT", type=["pdf", "docx", "txt"])

        if uploaded_file is not None and st.button("Upload", type="primary"):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            try:
                resp = requests.post(
                    api_url(base_url, "/documents/upload"),
                    headers=auth_headers(),
                    files=files,
                    timeout=60,
                )
            except requests.RequestException as exc:
                st.error(f"Could not reach the API: {exc}")
            else:
                if resp.status_code == 201:
                    data = resp.json()
                    st.success(data.get("message", "Uploaded."))
                    st.session_state.selected_doc_id = data["document"]["id"]
                    st.rerun()
                else:
                    st.error(resp.json().get("detail", "Upload failed"))

    with manual_tab:
        with st.form("manual_text_form"):
            title = st.text_input("Title", placeholder="e.g. Meeting notes - July 8")
            text = st.text_area("Paste or type your text", height=250)
            submitted = st.form_submit_button("Add document", type="primary")

        if submitted:
            if not title.strip() or not text.strip():
                st.error("Please provide both a title and some text.")
            else:
                try:
                    resp = requests.post(
                        api_url(base_url, "/documents/manual"),
                        headers=auth_headers(),
                        json={"title": title, "text": text},
                        timeout=30,
                    )
                except requests.RequestException as exc:
                    st.error(f"Could not reach the API: {exc}")
                else:
                    if resp.status_code == 201:
                        data = resp.json()
                        st.success(data.get("message", "Added."))
                        st.session_state.selected_doc_id = data["document"]["id"]
                        st.rerun()
                    else:
                        st.error(resp.json().get("detail", "Could not add text"))


def fetch_documents(q: str | None = None) -> list:
    params = {"q": q} if q else None
    try:
        resp = requests.get(api_url(base_url, "/documents"), headers=auth_headers(), params=params, timeout=15)
    except requests.RequestException as exc:
        st.error(f"Could not reach the API: {exc}")
        return []
    if resp.status_code == 200:
        return resp.json()
    st.error(resp.json().get("detail", "Could not load documents"))
    return []


STATUS_BADGES = {
    "pending": "🕓 pending",
    "processing": "⚙️ processing",
    "completed": "✅ completed",
    "failed": "❌ failed",
}


def render_documents_tab():
    st.subheader("Your documents")

    search_cols = st.columns([4, 1])
    search_query = search_cols[0].text_input(
        "Search by document ID or filename", placeholder="e.g. 3  or  invoice", key="doc_search"
    )
    if search_cols[1].button("🔄 Refresh", use_container_width=True):
        st.rerun()

    documents = fetch_documents(q=search_query.strip() if search_query else None)
    if not documents:
        if search_query:
            st.info(f"No documents match '{search_query}'.")
        else:
            st.info("No documents yet — add one in the Upload tab.")
        return

    for doc in documents:
        badge = STATUS_BADGES.get(doc["processing_status"], doc["processing_status"])

        with st.container(border=True):
            cols = st.columns([1, 3, 2, 2, 2])
            cols[0].caption(f"ID {doc['id']}")
            cols[1].markdown(f"**{doc['filename']}**")
            cols[2].caption(f"{doc['file_size_bytes'] / 1024:.1f} KB")
            cols[3].caption(doc["uploaded_at"][:19].replace("T", " "))
            cols[4].markdown(badge)

            action_cols = st.columns(5)

            # View Text
            if action_cols[0].button("View text", key=f"text_{doc['id']}"):
                st.session_state.selected_doc_id = doc["id"]
                st.session_state[f"show_text_{doc['id']}"] = True

            # View Analysis
            if action_cols[1].button("View analysis", key=f"analysis_{doc['id']}"):
                st.session_state.selected_doc_id = doc["id"]
                st.session_state[f"show_analysis_{doc['id']}"] = True

            # Ask Question
            if action_cols[2].button("Ask a question", key=f"select_{doc['id']}"):
                st.session_state.selected_doc_id = doc["id"]
                st.toast(f"Selected '{doc['filename']}' — go to the Ask Questions tab")

            # Export to Word
            with action_cols[3]:
                cache_key = f"export_bytes_{doc['id']}"
                if st.session_state.get(cache_key) is not None:
                    st.download_button(
                        "📄 Save .docx",
                        data=st.session_state[cache_key],
                        file_name=f"{doc['filename'].rsplit('.', 1)[0]}_export.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"download_{doc['id']}",
                    )
                else:
                    if st.button("📄 Export .docx", key=f"export_{doc['id']}"):
                        try:
                            export_resp = requests.get(
                                api_url(base_url, f"/documents/{doc['id']}/export"),
                                headers=auth_headers(),
                                timeout=30,
                            )
                        except requests.RequestException as exc:
                            st.error(f"Could not reach the API: {exc}")
                        else:
                            if export_resp.status_code == 200:
                                st.session_state[cache_key] = export_resp.content
                                st.rerun()
                            else:
                                st.error("Export failed")

            # Delete Document
            if action_cols[4].button("🗑️ Delete", key=f"delete_{doc['id']}"):
                try:
                    resp = requests.delete(
                        api_url(base_url, f"/documents/{doc['id']}"),
                        headers=auth_headers(),
                        timeout=15,
                    )

                    if resp.status_code == 200:
                        st.success("Document deleted successfully.")
                        st.rerun()
                    else:
                        st.error(resp.json().get("detail", "Delete failed"))

                except requests.RequestException as exc:
                    st.error(f"Could not reach the API: {exc}")

            # Show Extracted Text
            if st.session_state.get(f"show_text_{doc['id']}"):
                try:
                    detail_resp = requests.get(
                        api_url(base_url, f"/documents/{doc['id']}"),
                        headers=auth_headers(),
                        timeout=15,
                    )

                    st.text_area(
                        "Extracted text",
                        detail_resp.json().get("extracted_text", ""),
                        height=200,
                        key=f"text_area_{doc['id']}",
                    )

                except requests.RequestException as exc:
                    st.error(f"Could not reach the API: {exc}")

            # Show AI Analysis
            if st.session_state.get(f"show_analysis_{doc['id']}"):
                try:
                    analysis_resp = requests.get(
                        api_url(base_url, f"/documents/{doc['id']}/analysis"),
                        headers=auth_headers(),
                        timeout=15,
                    )

                except requests.RequestException as exc:
                    st.error(f"Could not reach the API: {exc}")

                else:
                    if analysis_resp.status_code == 200:
                        analysis = analysis_resp.json()

                        st.markdown("**Summary**")
                        st.write(analysis["summary"])

                        st.markdown("**Key Points**")
                        for point in analysis["key_points"]:
                            st.markdown(f"- {point}")

                        st.markdown("**Important Topics**")
                        for topic in analysis["important_topics"]:
                            st.markdown(f"- {topic}")

                    else:
                        st.info(
                            analysis_resp.json().get(
                                "detail",
                                "Analysis not ready yet"
                            )
                        )


def render_ask_tab():
    st.subheader("Ask a question about a document")

    documents = fetch_documents()
    if not documents:
        st.info("No documents yet — upload one in the Upload tab.")
        return

    doc_labels = {doc["id"]: doc["filename"] for doc in documents}
    default_index = 0
    doc_ids = list(doc_labels.keys())
    if st.session_state.selected_doc_id in doc_ids:
        default_index = doc_ids.index(st.session_state.selected_doc_id)

    selected_id = st.selectbox(
        "Document",
        options=doc_ids,
        format_func=lambda i: doc_labels[i],
        index=default_index,
    )
    st.session_state.selected_doc_id = selected_id

    question = st.text_input("Your question")
    if st.button("Ask", type="primary") and question:
        try:
            resp = requests.post(
                api_url(base_url, f"/documents/{selected_id}/ask"),
                headers=auth_headers(),
                json={"question": question},
                timeout=60,
            )
        except requests.RequestException as exc:
            st.error(f"Could not reach the API: {exc}")
        else:
            if resp.status_code == 201:
                answer = resp.json()["answer"]
                st.markdown("**Answer**")
                st.write(answer)
            else:
                st.error(resp.json().get("detail", "Could not get an answer"))

    st.divider()
    st.markdown("**Previous questions for this document**")
    try:
        history_resp = requests.get(
            api_url(base_url, f"/documents/{selected_id}/questions"), headers=auth_headers(), timeout=15
        )
    except requests.RequestException as exc:
        st.error(f"Could not reach the API: {exc}")
        return

    if history_resp.status_code == 200:
        history = history_resp.json()
        if not history:
            st.caption("No questions asked yet.")
        for qa in reversed(history):
            with st.expander(qa["question"]):
                st.write(qa["answer"])
                st.caption(qa["created_at"][:19].replace("T", " "))


def render_app():
    st.title("📚 AI-Powered Knowledge Base")
    upload_tab, documents_tab, ask_tab = st.tabs(["⬆️ Upload", "📄 Documents", "💬 Ask Questions"])

    with upload_tab:
        render_upload_tab()
    with documents_tab:
        render_documents_tab()
    with ask_tab:
        render_ask_tab()




# ------------------------------------------------------------------ #
# Entrypoint
# ------------------------------------------------------------------ #
if st.session_state.token is None:
    render_auth_screen()
else:
    render_app()