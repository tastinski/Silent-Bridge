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
# Используем Flash, он быстрее и дешевле для видео
model = genai.GenerativeModel('gemini-1.5-flash')

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
    # Создаем временный файл, так как Gemini API требует путь к файлу
    suffix = "." + uploaded_file.name.split('.')[-1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name

    try:
        with st.spinner(f"📤 Загружаю {uploaded_file.name} в нейросеть..."):
            gemini_file = genai.upload_file(tmp_path)
            
        # Для видео нужно ждать завершения обработки (State: ACTIVE)
        while gemini_file.state.name == "PROCESSING":
            with st.spinner("⏳ Нейросеть смотрит видео..."):
                time.sleep(2)
                gemini_file = genai.get_file(gemini_file.name)
        
        if gemini_file.state.name == "FAILED":
            raise ValueError("Не удалось обработать видео.")
            
        return gemini_file
    finally:
        # Удаляем временный файл с диска сервера
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

# --- 3. ИНТЕРФЕЙС ---
st.title("🧬 Silent Bridge: AI-Консилиум")
st.markdown("Загрузите выписки (PDF), фото или **видео поведения**. ИИ изучит их и даст заключение.")

# Боковая панель
with st.sidebar:
    st.header("📂 Материалы дела")
    # Добавили mp4, mov, avi
    uploaded_files = st.file_uploader(
        "Загрузить документы/видео", 
        type=['pdf', 'txt', 'png', 'jpg', 'jpeg', 'mp4', 'mov', 'avi'], 
        accept_multiple_files=True
    )
    
    if st.button("🗑️ Сбросить диалог"):
        st.session_state.messages = []
        st.rerun()

# --- 4. ПОДГОТОВКА КОНТЕНТА ---
# Мы собираем контент для ПЕРВОГО запроса (текст + файлы)
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
            # Это ФОТО или ВИДЕО -> Грузим через File API
            try:
                gemini_file = upload_to_gemini(file)
                request_content.append(gemini_file) # Добавляем сам объект файла
                st.sidebar.success(f"✅ {file.name} загружен!")
            except Exception as e:
                st.sidebar.error(f"Ошибка с {file.name}: {e}")

# --- 5. ЧАТ-БОТ ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({"role": "assistant", "content": "Я готов. Загружайте видео, фото или документы."})

# Показываем историю
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        # Если в истории есть объекты файлов (они не отображаются как текст), пропускаем их при рендере
        if isinstance(msg["content"], str):
            st.markdown(msg["content"])

# Логика ответа
if user_input := st.chat_input("Ваш вопрос или комментарий..."):
    # 1. Показываем вопрос юзера
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 2. Формируем запрос
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        try:
            # История чата для модели
            history = []
            # Пропускаем системные сообщения и собираем историю
            for m in st.session_state.messages[:-1]:
                # В истории могут быть старые текстовые ответы, но файлы мы передаем только в текущем контексте (или храним ссылки)
                # Упрощение: для мультимодального чата лучше каждый раз передавать контекст файлов, если он свежий
                pass 

            # Собираем ТЕКУЩЕЕ сообщение: [Текст промпта + Файлы + Вопрос юзера]
            # Если это самое начало диалога и есть файлы
            if has_files and len(st.session_state.messages) < 3:
                # Добавляем наш мощный промпт к вопросу
                final_parts = [ANALYSIS_PROMPT.format(text="[См. приложенные файлы]")] 
                # Сначала файлы, потом текст
                for item in request_content:
                    final_parts.append(item)
                final_parts.append("\n\nВопрос/Комментарий пользователя: " + user_input)
            else:
                # Обычный диалог
                final_parts = []
                # Если файлы только что загрузили, добавляем их
                if request_content: 
                     for item in request_content:
                        final_parts.append(item)
                final_parts.append(user_input)

            # Запускаем чат (в данном случае проще single request с историей, но для файлов лучше generate_content)
            # Внимание: history в gemini с файлами работает хитро. Проще каждый раз отправлять generate_content с list of messages, но st.chat_input это single turn.
            
            # Используем chat session, но файлы посылаем в текущем сообщении
            chat = model.start_chat(history=[]) 
            
            # Safety settings
            safety = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
            
            response = chat.send_message(final_parts, safety_settings=safety)
            
            message_placeholder.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})

        except Exception as e:
            st.error(f"Ошибка: {e}")
