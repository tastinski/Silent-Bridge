import streamlit as st
import google.generativeai as genai
from prompts import ANALYSIS_PROMPT

# --- 1. АВТОРИЗАЦИЯ ---
if "GOOGLE_API_KEY" in st.secrets:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
else:
    GOOGLE_API_KEY = st.text_input("🔐 Введи свой Google API Key:", type="password")

if not GOOGLE_API_KEY:
    st.info("👈 Введи ключ, чтобы начать диалог.")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)

# Авто-выбор модели
def get_best_model():
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        flash = next((m for m in models if 'flash' in m), None)
        return flash if flash else (models[0] if models else "gemini-pro")
    except:
        return "gemini-pro"

model = genai.GenerativeModel(get_best_model())

# --- 2. ИНТЕРФЕЙС ЧАТА ---
st.set_page_config(page_title="Silent Bridge Chat", page_icon="🌉")
st.title("🌉 Silent Bridge: Диалог")

# Инициализация памяти (истории переписки)
if "messages" not in st.session_state:
    st.session_state.messages = []
    # Первое сообщение от бота
    st.session_state.messages.append({
        "role": "assistant", 
        "content": "Привет! Я готов к работе. Отправь мне текст выписки или анализов, и я разберу их."
    })

# Отображаем всю историю на экране
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 3. ОБРАБОТКА НОВОГО СООБЩЕНИЯ ---
if user_input := st.chat_input("Напиши сообщение..."):
    # 1. Показываем сообщение пользователя
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 2. Формируем ответ
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        try:
            # ЛОГИКА: Если это ПЕРВОЕ сообщение пользователя (длинное), добавляем к нему нашу ИНСТРУКЦИЮ.
            # Если это второе, третье и т.д. — просто отправляем как есть.
            
            # Считаем сообщения пользователя в истории
            user_msg_count = sum(1 for m in st.session_state.messages if m["role"] == "user")
            
            if user_msg_count == 1:
                # Это первый заход -> Оборачиваем в твой мощный Промпт
                final_text_to_send = ANALYSIS_PROMPT.format(text=user_input)
            else:
                # Это просто вопрос -> Шлем как есть
                final_text_to_send = user_input

            # Собираем историю для Google Gemini (чтобы он помнил контекст)
            chat_history = []
            # Берем всё, кроме последнего (его мы шлем отдельно)
            for msg in st.session_state.messages[:-1]:
                role = "user" if msg["role"] == "user" else "model"
                # Пропускаем приветствие бота, чтобы не сбивать модель
                if msg["content"].startswith("Привет! Я готов"):
                    continue
                chat_history.append({"role": role, "parts": [msg["content"]]})

            # Запускаем чат с историей
            chat = model.start_chat(history=chat_history)
            
            # Настройки безопасности (Бесстрашие)
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]

            # Получаем ответ
            response = chat.send_message(final_text_to_send, safety_settings=safety_settings)
            
            # Показываем ответ
            message_placeholder.markdown(response.text)
            
            # Сохраняем ответ бота в историю
            st.session_state.messages.append({"role": "assistant", "content": response.text})

        except Exception as e:
            st.error(f"Ошибка: {e}")
