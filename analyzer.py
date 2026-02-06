import streamlit as st
import google.generativeai as genai
import PyPDF2
from prompts import ANALYSIS_PROMPT
import tempfile
import time
import os

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

# --- УМНЫЙ ВЫБОР МОДЕЛИ (Чтобы не было ошибки 404) ---
def get_best_model():
    try:
        # Получаем список всех доступных моделей
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # Ищем модель со словом 'flash' (она быстрая и видит видео)
        flash_model = next((m for m in models if 'flash' in m), None)
        # Если нет Flash, ищем Pro, иначе берем первую попавшуюся
        best_model = flash_model if flash_model else (next((m for m in models if 'pro' in m), models[0]))
        return best_model
    except Exception as e:
        # Если совсем всё сломалось, пробуем стандартную 2.0 (она новее)
        return "models/gemini-2.0-flash"

selected_model_name = get_best_model()
# Показываем юзеру, какую модель выбрали (для отладки)
st.sidebar.caption(f"🤖 Модель: {selected_model_name}")

model = genai.GenerativeModel(selected_model_name)

# --- 2. ФУНКЦИИ ЗАГРУЗКИ ---
def extract_text_from_pdf(uploaded_file):
    try:
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        return f"Ошибка чтения PDF: {e}"

def upload_to_gemini(uploaded_file):
    """Сохраняет файл временно, грузит в Gemini и ждет обработки"""
    suffix = "." + uploaded_file.name.split('.')[-1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name

    try:
        with st.spinner(f"📤 Загружаю {uploaded_file.name} в нейросеть..."):
            gemini_file = genai.upload_file(tmp_path)
            
        # Для видео нужно ждать завершения обработки
        while gemini_file.state.name == "PROCESSING":
            with st.spinner("⏳ Нейросеть смотрит видео..."):
                time.sleep(2)
                gemini_file = genai.get_file(gemini_file.name)
        
        if gemini_file.state.name == "FAILED":
            raise ValueError("Не удалось обработать видео.")
            
        return gemini_file
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

# --- 3. ИНТЕРФЕЙС ---
st.title("🧬 Silent Bridge: AI-Консилиум")
st.markdown("Загрузите выписки (PDF), фото или **видео поведения**. ИИ изучит их и даст заключение.")

# Боковая панель
with st.sidebar:
    st.header("📂 Материалы дела")
    uploaded_files = st.file_uploader(
        "Загрузить документы/видео", 
        type=['pdf', 'txt', 'png', 'jpg', 'jpeg', 'mp4', 'mov', 'avi'], 
        accept_multiple_files=True
    )
    
    if st.button("🗑️ Сбросить диалог"):
        st.session_state.messages = []
        st.rerun()

# --- 4. ПОДГОТОВКА КОНТЕНТА ---
request_content = []
has_files = False

if uploaded_files:
    has_files = True
    for file in uploaded_files:
        if file.type == "application/pdf":
            text = extract_text_from_pdf(file)
            request_content.append(f"\n--- ДОКУМЕНТ {file.name} ---\n{text}\n")
        elif file.type.startswith("text"):
            stringio = file.getvalue().decode("utf-8")
            request_content.append(f"\n--- ТЕКСТ {file.name} ---\n{stringio}\n")
        else:
            try:
                gemini_file = upload_to_gemini(file)
                request_content.append(gemini_file)
                st.sidebar.success(f"✅ {file.name} загружен!")
            except Exception as e:
                st.sidebar.error(f"Ошибка с {file.name}: {e}")

# --- 5. ЧАТ-БОТ ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({"role": "assistant", "content": "Я готов. Загружайте видео, фото или документы."})

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if isinstance(msg["content"], str):
            st.markdown(msg["content"])

if user_input := st.chat_input("Ваш вопрос или комментарий..."):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        try:
            # Собираем ТЕКУЩЕЕ сообщение
            if has_files and len(st.session_state.messages) < 3:
                final_parts = [ANALYSIS_PROMPT.format(text="[См. приложенные файлы]")]
                for item in request_content:
                    final_parts.append(item)
                final_parts.append("\n\nВопрос пользователя: " + user_input)
            else:
                final_parts = []
                if request_content:
                    for item in request_content:
                        final_parts.append(item)
                final_parts.append(user_input)

            # Создаем чат без истории, так проще передавать файлы
            chat = model.start_chat(history=[])
            
            safety = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
            
            response = chat.send_message(final_parts, safety_settings=safety)
            
            message_placeholder.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})

        except Exception as e:
            st.error(f"Ошибка: {e}")
