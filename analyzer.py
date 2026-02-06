import streamlit as st
import google.generativeai as genai
import PyPDF2
from prompts import ANALYSIS_PROMPT
import tempfile
import time
import os
import requests  # Добавили для связи с API

# --- 1. НАСТРОЙКИ И АВТОРИЗАЦИЯ ---
st.set_page_config(page_title="Silent Bridge AI", page_icon="🧬", layout="wide")

if "GOOGLE_API_KEY" in st.secrets:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
else:
    GOOGLE_API_KEY = st.text_input("🔐 Введи API Key:", type="password")

if not GOOGLE_API_KEY:
    st.warning("👈 Нужен ключ для запуска.")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)

def get_best_model():
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        flash_model = next((m for m in models if 'flash' in m), None)
        return flash_model if flash_model else "models/gemini-2.0-flash"
    except:
        return "models/gemini-2.0-flash"

selected_model = get_best_model()
st.sidebar.caption(f"🤖 Модель: {selected_model}")
model = genai.GenerativeModel(selected_model)

# --- 2. ФУНКЦИИ ОБРАБОТКИ ---
def extract_text_from_pdf(uploaded_file):
    try:
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        return f"Ошибка чтения PDF: {e}"

# --- 3. ИНТЕРФЕЙС ---
st.title("🧬 Silent Bridge: AI-Консилиум")
st.markdown("Загрузите выписки (PDF) или **видео**. Данные будут отправлены нейробиологу через API.")

with st.sidebar:
    st.header("📂 Материалы дела")
    uploaded_files = st.file_uploader(
        "Загрузить файлы", 
        type=['pdf', 'txt', 'png', 'jpg', 'jpeg', 'mp4', 'mov', 'avi'], 
        accept_multiple_files=True
    )
    if st.button("🗑️ Сбросить диалог"):
        st.session_state.messages = []
        st.rerun()

# --- 4. ЛОГИКА ЧАТА И API ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# Отображение истории
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if user_input := st.chat_input("Напиши вопрос (например: 'Сделай разбор видео')..."):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        try:
            # 1. Отправка файлов на API
            st.info("📡 Передача данных нейробиологу (API)...")
            
            # Подготовка файлов для корректной отправки всех видео сразу
            files_to_send = []
            if uploaded_files:
                for f in uploaded_files:
                    files_to_send.append(('files', (f.name, f.getvalue(), f.type)))

            # Твой API эндпоинт (проверь порт!)
            api_url = "http://127.0.0.1:8000/analyze"
            response = requests.post(api_url, files=files_to_send, data={"prompt": user_input})

            if response.status_code == 200:
                # 2. Опрос результата (Polling)
                finished = False
                max_retries = 30  # Ждем максимум 2.5 минуты
                retries = 0
                
                while not finished and retries < max_retries:
                    with st.spinner("🧠 Нейробиолог изучает данные..."):
                        time.sleep(5)
                        # Запрашиваем готовность
                        res = requests.get("http://127.0.0.1:8000/get_result")
                        data = res.json()
                        
                        if data.get("status") == "completed":
                            final_result = data.get("analysis_result")
                            message_placeholder.markdown(final_result)
                            st.session_state.messages.append({"role": "assistant", "content": final_result})
                            finished = True
                        else:
                            retries += 1
                
                if not finished:
                    st.error("Таймаут: Бэкенд слишком долго думает.")
            else:
                st.error(f"Ошибка API: {response.status_code}. Проверь, запущен ли сервер бэкенда.")
                
        except Exception as e:
            st.error(f"Не удалось связаться с бэкендом: {e}")
