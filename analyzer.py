import streamlit as st
import google.generativeai as genai
import PyPDF2
from prompts import ANALYSIS_PROMPT
import tempfile
import time

if response.status_code == 200:
    st.info("Файлы ушли нейробиологу. Ждем результат...")
    
    # Допустим, API возвращает task_id. Если нет, просто опрашивай эндпоинт результата.
    finished = False
    while not finished:
        result_check = requests.get("http://127.0.0.1:8000/get_result") 
        data = result_check.json()
        
        if data.get("status") == "completed":
            st.success("Анализ готов!")
            st.write(data.get("analysis_result"))
            finished = True
        else:
            time.sleep(5) # Ждем 5 секунд перед новой проверкой
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

# --- УМНЫЙ ВЫБОР МОДЕЛИ ---
def get_best_model():
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # Ищем Flash (она видит видео и быстрая)
        flash_model = next((m for m in models if 'flash' in m), None)
        return flash_model if flash_model else "models/gemini-2.0-flash"
    except:
        return "models/gemini-2.0-flash"

selected_model = get_best_model()
st.sidebar.caption(f"🤖 Модель: {selected_model}")
model = genai.GenerativeModel(selected_model)

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
    """Грузит файл в Gemini и кэширует результат в session_state"""
    # Проверяем, загружали ли мы этот файл уже (чтобы не ждать каждый раз)
    if "uploaded_files_cache" not in st.session_state:
        st.session_state.uploaded_files_cache = {}
        
    if uploaded_file.name in st.session_state.uploaded_files_cache:
        return st.session_state.uploaded_files_cache[uploaded_file.name]

    # Если не загружали — грузим
    suffix = "." + uploaded_file.name.split('.')[-1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name

    try:
        with st.spinner(f"📤 Загружаю {uploaded_file.name} в нейросеть..."):
            gemini_file = genai.upload_file(tmp_path)
            
        # Ждем обработки (для видео)
        while gemini_file.state.name == "PROCESSING":
            with st.spinner("⏳ Видео обрабатывается..."):
                time.sleep(2)
                gemini_file = genai.get_file(gemini_file.name)
        
        if gemini_file.state.name == "FAILED":
            raise ValueError("Ошибка обработки файла на стороне Google.")
            
        # Сохраняем в кэш
        st.session_state.uploaded_files_cache[uploaded_file.name] = gemini_file
        return gemini_file
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

# --- 3. ИНТЕРФЕЙС ---
st.title("🧬 Silent Bridge: AI-Консилиум")
st.markdown("Загрузите выписки (PDF) или **видео**. ИИ даст клинический разбор.")

# Боковая панель
with st.sidebar:
    st.header("📂 Материалы дела")
    uploaded_files = st.file_uploader(
        "Загрузить файлы", 
        type=['pdf', 'txt', 'png', 'jpg', 'jpeg', 'mp4', 'mov', 'avi'], 
        accept_multiple_files=True
    )
    
    if st.button("🗑️ Сбросить диалог"):
        st.session_state.messages = []
        if "uploaded_files_cache" in st.session_state:
            st.session_state.uploaded_files_cache = {}
        st.rerun()

# --- 4. ПОДГОТОВКА КОНТЕНТА ---
request_content = []
has_files = False

if uploaded_files:
    has_files = True
    for file in uploaded_files:
        if file.type == "application/pdf":
            text = extract_text_from_pdf(file)
            request_content.append(f"\n--- PDF {file.name} ---\n{text}\n")
        elif file.type.startswith("text"):
            stringio = file.getvalue().decode("utf-8")
            request_content.append(f"\n--- TXT {file.name} ---\n{stringio}\n")
        else:
            # Фото и Видео
            try:
                g_file = upload_to_gemini(file)
                request_content.append(g_file)
                st.sidebar.success(f"✅ {file.name} готов!")
            except Exception as e:
                st.sidebar.error(f"Ошибка {file.name}: {e}")

# --- 5. ЧАТ ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({"role": "assistant", "content": "Я готов. Загрузите файлы и задайте вопрос."})

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if isinstance(msg["content"], str):
            st.markdown(msg["content"])

if user_input := st.chat_input("Напиши вопрос (например: 'Сделай разбор видео')..."):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        try:
            # 🔥 ГЛАВНОЕ ИЗМЕНЕНИЕ:
            # Если есть файлы, мы ВСЕГДА добавляем инструкцию Врача (ANALYSIS_PROMPT),
            # чтобы он не забывал роль, даже если это 10-й вопрос.
            
            final_parts = []
            
            if has_files:
                # 1. Сначала инструкция (Промпт)
                final_parts.append(ANALYSIS_PROMPT.format(text="[См. материалы ниже]"))
                # 2. Потом сами файлы
                for item in request_content:
                    final_parts.append(item)
                # 3. Потом вопрос юзера
                final_parts.append("\n\nЗАДАЧА / ВОПРОС ПОЛЬЗОВАТЕЛЯ: " + user_input)
            else:
                # Если файлов нет, просто болтаем
                final_parts.append(user_input)

            # Запускаем генерацию (без истории, так надежнее для файлов)
            chat = model.start_chat(history=[])
            
            safety = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
            
            with st.spinner("🧠 Консилиум думает..."):
                response = chat.send_message(final_parts, safety_settings=safety)
            
            message_placeholder.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})

        except Exception as e:
            st.error(f"Ошибка: {e}")
