import streamlit as st
import google.generativeai as genai
import requests
import time
import uuid

# ---------------- CONFIG ----------------

st.set_page_config(
    page_title="Silent Bridge AI",
    page_icon="🧬",
    layout="wide"
)

# ---------------- API KEY ----------------

if "GOOGLE_API_KEY" in st.secrets:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
else:
    GOOGLE_API_KEY = st.text_input("🔐 Enter Google API Key", type="password")

if not GOOGLE_API_KEY:
    st.warning("Enter API key to continue")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)

# ---------------- MODEL AUTO SELECT ----------------

def get_best_model():
    try:
        models = [
            m.name for m in genai.list_models()
            if 'generateContent' in m.supported_generation_methods
        ]
        flash = next((m for m in models if "flash" in m.lower()), None)
        return flash if flash else "models/gemini-2.0-flash"
    except:
        return "models/gemini-2.0-flash"

MODEL_NAME = get_best_model()
st.sidebar.caption(f"Model: {MODEL_NAME}")

# ---------------- BACKEND CONFIG ----------------

API_BASE = "http://127.0.0.1:8000"

# ---------------- UI ----------------

st.title("🧬 Silent Bridge — Case Analysis")

with st.sidebar:
    st.header("Case Files")

    uploaded_files = st.file_uploader(
        "Upload documents / video",
        type=["pdf", "txt", "png", "jpg", "jpeg", "mp4", "mov", "avi"],
        accept_multiple_files=True
    )

    if st.button("Reset Chat"):
        st.session_state.messages = []
        st.session_state.job_id = None
        st.rerun()

# ---------------- SESSION ----------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "job_id" not in st.session_state:
    st.session_state.job_id = None

# ---------------- CHAT HISTORY ----------------

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ---------------- MAIN CHAT ----------------

user_input = st.chat_input("Ask about case / video / documents")

if user_input:

    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):

        placeholder = st.empty()

        try:
            # ---------- PREP FILES ----------
            files_payload = []

            if uploaded_files:
                for f in uploaded_files:
                    files_payload.append(
                        ("files", (f.name, f.getvalue(), f.type))
                    )

            # ---------- CREATE JOB ----------
            job_id = str(uuid.uuid4())
            st.session_state.job_id = job_id

            st.info("Sending case to backend...")

            res = requests.post(
                f"{API_BASE}/analyze",
                files=files_payload,
                data={
                    "prompt": user_input,
                    "job_id": job_id
                },
                timeout=120
            )

            if res.status_code != 200:
                st.error(f"Backend error: {res.status_code}")
                st.stop()

            # ---------- POLLING RESULT ----------
            finished = False
            max_checks = 40
            checks = 0

            while not finished and checks < max_checks:

                with st.spinner("AI analyzing case..."):
                    time.sleep(3)

                r = requests.get(
                    f"{API_BASE}/result/{job_id}",
                    timeout=30
                )

                data = r.json()

                if data.get("status") == "completed":

                    result = data.get("result", "No result")

                    placeholder.markdown(result)

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": result
                    })

                    finished = True

                elif data.get("status") == "failed":
                    st.error("Analysis failed")
                    finished = True
                else:
                    checks += 1

            if not finished:
                st.error("Timeout waiting for result")

        except Exception as e:
            st.error(f"Connection error: {e}")

