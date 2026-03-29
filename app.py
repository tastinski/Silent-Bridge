import streamlit as st
from openai import OpenAI
import base64
import fitz
from prompt import SYSTEM_PROMPT, VIDEO_PROMPT, WELCOME_MESSAGE
from deep_analysis_prompt import DEEP_ANALYSIS_PROMPT
from council import run_council_sync

st.set_page_config(page_title="Yasno", page_icon="🌉", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.stApp { background-color: #0F1923; color: #E8E4DC; }
[data-testid="stSidebar"] { background-color: #141F2B; border-right: 1px solid #1E2D3D; }
p, span, li, label { color: #E8E4DC !important; }
.stMarkdown p, .stMarkdown li { color: #E8E4DC !important; font-size: 15px !important; line-height: 1.8 !important; }
[data-testid="stChatMessage"] { background-color: #141F2B; border: 1px solid #1E2D3D; border-radius: 12px; margin-bottom: 8px; }
[data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li { color: #E8E4DC !important; font-size: 15px !important; line-height: 1.8 !important; }
[data-testid="stChatMessage"] h1, [data-testid="stChatMessage"] h2, [data-testid="stChatMessage"] h3 { color: #FFFFFF !important; }
[data-testid="stChatInput"] textarea { background-color: #141F2B !important; color: #E8E4DC !important; border: 1px solid #1E2D3D !important; border-radius: 12px !important; }
h1, h2, h3 { color: #E8E4DC !important; }
.stButton > button { background-color: #1A73C8; color: white; border: none; border-radius: 8px; padding: 8px 16px; width: 100%; }
.stButton > button:hover { background-color: #1558A0; }
#MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# API KEY
if "OPENAI_API_KEY" in st.secrets:
    api_key = st.secrets["OPENAI_API_KEY"]
else:
    api_key = st.sidebar.text_input("OpenAI API Key", type="password", placeholder="sk-...")

if not api_key:
    st.markdown("<div style='text-align:center;padding:60px 20px;'><h1 style='color:#E8E4DC;'>🌉 Yasno</h1><p style='color:#8AADCC;'>Введите API ключ в боковой панели</p></div>", unsafe_allow_html=True)
    st.stop()

client = OpenAI(api_key=api_key)

def extract_pdf_text(file_bytes):
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text.strip()
    except Exception as e:
        return f"Ошибка чтения PDF: {e}"

def encode_image(file_bytes):
    return base64.b64encode(file_bytes).decode("utf-8")

def build_messages(user_text, uploaded_files, history):
    mode = st.session_state.get("analysis_mode", "Обычный разговор")
    if mode == "Глубокий анализ":
        system = DEEP_ANALYSIS_PROMPT
    else:
        system = SYSTEM_PROMPT

    messages = [{"role": "system", "content": system}]
    for msg in history[-6:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    content = []
    if uploaded_files:
        for f in uploaded_files:
            file_bytes = f.getvalue()
            if f.type == "application/pdf":
                pdf_text = extract_pdf_text(file_bytes)
                content.append({"type": "text", "text": "[Документ: " + f.name + "]\n\n" + pdf_text})
            elif f.type.startswith("image/"):
                b64 = encode_image(file_bytes)
                content.append({"type": "image_url", "image_url": {"url": "data:" + f.type + ";base64," + b64, "detail": "high"}})
            elif f.type == "text/plain":
                text = file_bytes.decode("utf-8", errors="ignore")
                content.append({"type": "text", "text": "[Файл: " + f.name + "]\n\n" + text})
            elif f.type.startswith("video/"):
                content.append({"type": "text", "text": "[Видео: " + f.name + "] Опишите что происходит в видео."})

    if user_text:
        content.append({"type": "text", "text": user_text})

    messages.append({"role": "user", "content": content if len(content) > 1 else user_text})
    return messages

def get_response(messages):
    return client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=2000,
        temperature=0.3,
        stream=True
    )

# SIDEBAR
with st.sidebar:
    st.markdown("<div style='text-align:center;padding:16px 0 8px;'><h2 style='color:#E8E4DC;margin:0;'>🌉 Yasno</h2><p style='color:#8AADCC;font-size:12px;margin:4px 0 0;'>Навигатор для семей с аутизмом</p></div>", unsafe_allow_html=True)
    st.divider()

    st.markdown("**Загрузите файлы**")
    uploaded_files = st.file_uploader("PDF, фото, текст", type=["pdf","txt","png","jpg","jpeg","mp4","mov"], accept_multiple_files=True, label_visibility="collapsed")
    if uploaded_files:
        for f in uploaded_files:
            icon = "📄" if "pdf" in f.type else "🖼️" if "image" in f.type else "🎥" if "video" in f.type else "📝"
            st.markdown("<small>" + icon + " " + f.name + "</small>", unsafe_allow_html=True)

    st.divider()
    st.markdown("**Режим анализа**")
    analysis_mode = st.radio("", ["Обычный разговор", "Глубокий анализ"], label_visibility="collapsed")
    st.session_state.analysis_mode = analysis_mode

    st.divider()
    st.markdown("**Быстрый старт**")
    if st.button("📄 Расшифровать документ"):
        st.session_state.quick_input = "Расшифруй этот документ простыми словами"
    if st.button("❓ Вопросы для врача"):
        st.session_state.quick_input = "Какие вопросы задать врачу по этому документу"
    if st.button("🏛️ Консилиум специалистов"):
        st.session_state.run_council = True
        st.session_state.council_question = ""
    if st.button("🗑️ Очистить чат"):
        st.session_state.messages = []
        st.session_state.quick_input = ""
        st.session_state.run_council = False
        st.rerun()

    st.divider()
    st.markdown("<div style='font-size:11px;color:#4A5568;line-height:1.5;'>Yasno — для разговора с врачом,<br>не вместо него.</div>", unsafe_allow_html=True)

# SESSION STATE
if "messages" not in st.session_state:
    st.session_state.messages = []
if "quick_input" not in st.session_state:
    st.session_state.quick_input = ""
if "run_council" not in st.session_state:
    st.session_state.run_council = False

# WELCOME
if not st.session_state.messages:
    st.markdown("<div style='background-color:#141F2B;border:1px solid #1E2D3D;border-radius:12px;padding:24px;margin-bottom:16px;'><p style='color:#E8E4DC;font-size:15px;line-height:1.8;margin:0;'>" + WELCOME_MESSAGE.replace("\n","<br>") + "</p></div>", unsafe_allow_html=True)

# CHAT HISTORY
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# COUNCIL MODE
if st.session_state.run_council and uploaded_files:
    st.session_state.run_council = False

    with st.chat_message("user"):
        st.markdown("Запустить консилиум специалистов")
    st.session_state.messages.append({"role": "user", "content": "Консилиум специалистов"})

    with st.chat_message("assistant"):
        with st.spinner("Консилиум читает документ... 15-20 секунд."):
            doc_text = ""
            for f in uploaded_files:
                file_bytes = f.getvalue()
                if f.type == "application/pdf":
                    doc_text += extract_pdf_text(file_bytes)
                elif f.type == "text/plain":
                    doc_text += file_bytes.decode("utf-8", errors="ignore")

            # Add last user question if exists
            last_q = ""
            for msg in reversed(st.session_state.messages):
                if msg["role"] == "user" and msg["content"] != "Консилиум специалистов":
                    last_q = msg["content"]
                    break

            council_input = doc_text
            if last_q:
                council_input = doc_text + "|||" + last_q

            if doc_text.strip():
                try:
                    result = run_council_sync(api_key, council_input)
                    st.markdown(result)
                    st.session_state.messages.append({"role": "assistant", "content": result})
                except Exception as e:
                    st.error("Ошибка консилиума: " + str(e))
            else:
                st.warning("Загрузите PDF документ для консилиума.")

elif st.session_state.run_council:
    st.session_state.run_council = False
    st.warning("Сначала загрузите документ.")

# CHAT INPUT
quick = st.session_state.get("quick_input", "")
if quick:
    st.session_state.quick_input = ""
    user_text = quick
else:
    user_text = st.chat_input("Напишите вопрос или загрузите документ...")

if user_text:
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.chat_message("user"):
        st.markdown(user_text)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""
        try:
            messages = build_messages(user_text, uploaded_files, st.session_state.messages[:-1])
            with st.spinner("Читаю..."):
                stream = get_response(messages)
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    full_response += delta
                    placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
        except Exception as e:
            placeholder.markdown("Ошибка: " + str(e))
