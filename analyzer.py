import streamlit as st
import google.generativeai as genai
import PyPDF2
from prompts import ANALYSIS_PROMPT

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
model = genai.GenerativeModel('gemini-1.5-flash')

# --- 2. ФУНКЦИИ "ЗРЕНИЯ" И "ЧТЕНИЯ" ---
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
st.markdown("Загрузите выписки (PDF) или фото анализов. ИИ изучит их и даст заключение.")

# Боковая панель для загрузки файлов
with st.sidebar:
    st.header("📂 Материалы дела")
    uploaded_files = st.file_uploader("Загрузить документы", type=['pdf', 'txt', 'png', 'jpg'], accept_multiple_files=True)
    
    # Кнопка очистки памяти
    if st.button("🗑️ Сбросить диалог"):
        st.session_state.messages = []
        st.experimental_rerun()

# --- 4. ОБРАБОТКА ФАЙЛОВ ---
file_content = ""
if uploaded_files:
    for file in uploaded_files:
        if file.type == "application/pdf":
            text = extract_text_from_pdf(file)
            file_content += f"\n--- ДОКУМЕНТ {file.name} ---\n{text}\n"
        elif file.type.startswith("image"):
            # Тут можно добавить OCR (распознавание фото), пока просто уведомляем
            st.info(f"📸 Изображение {file.name} принято к анализу (Vision Mode).")
            # Для простоты передаем имя, в будущем подключим Vision API
            file_content += f"\n[Загружено фото анализов: {file.name}]\n"
        else:
            stringio = file.getvalue().decode("utf-8")
            file_content += f"\n--- ТЕКСТ {file.name} ---\n{stringio}\n"

# --- 5. ЧАТ-БОТ С КОНТЕКСТОМ ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({"role": "assistant", "content": "Я готов. Загрузите файлы слева или напишите текст."})

# Показываем историю
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Логика ответа
if user_input := st.chat_input("Ваш вопрос или комментарий..."):
    # Добавляем вопрос юзера
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Формируем ПОЛНЫЙ контекст (Файлы + История + Текущий вопрос)
    with st.chat_message("assistant"):
        with st.spinner("🧠 Изучаю материалы дела..."):
            try:
                # Если загружены файлы и это первый вопрос — используем МОЩНЫЙ ПРОМПТ
                if file_content and len(st.session_state.messages) < 3:
                    final_prompt = ANALYSIS_PROMPT.format(text=file_content + "\n\nВопрос пользователя: " + user_input)
                else:
                    # Иначе просто поддерживаем диалог
                    final_prompt = user_input
                    if file_content:
                        final_prompt = f"Контекст из файлов:\n{file_content}\n\nВопрос: {user_input}"

                # История для модели
                history = []
                for m in st.session_state.messages[:-1]:
                    role = "model" if m["role"] == "assistant" else "user"
                    history.append({"role": role, "parts": [m["content"]]})

                chat = model.start_chat(history=history)
                response = chat.send_message(final_prompt)
                
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            
            except Exception as e:
                st.error(f"Ошибка: {e}")
