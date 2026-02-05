import streamlit as st
import google.generativeai as genai
from prompts import ANALYSIS_PROMPT  # <--- Самая важная строка: берем инструкцию из соседнего файла

# --- 1. БЕЗОПАСНАЯ АВТОРИЗАЦИЯ ---
# Проверяем, есть ли ключ в "сейфе" (Secrets). Если нет — просим ввести.
if "GOOGLE_API_KEY" in st.secrets:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
else:
    GOOGLE_API_KEY = st.text_input("🔐 Введи свой Google API Key:", type="password")

if not GOOGLE_API_KEY:
    st.info("👈 Введи ключ, чтобы запустить систему.")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)

# --- 2. НАСТРОЙКА МОЗГА (MODEL) ---
def get_best_model():
    try:
        # Ищем модели, доступные твоему ключу
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # Приоритет: Flash -> Pro -> Любая другая
        flash = next((m for m in models if 'flash' in m), None)
        return flash if flash else (models[0] if models else "gemini-pro")
    except:
        return "gemini-pro"

MODEL_NAME = get_best_model()
model = genai.GenerativeModel(MODEL_NAME)

# --- 3. ИНТЕРФЕЙС (UI) ---
st.set_page_config(page_title="Silent Bridge AI", page_icon="🌉")
st.title("🌉 Silent Bridge: AI Analytics")
st.caption(f"🚀 Система активна. Модель: **{MODEL_NAME}**")

def analyze_with_ai(text):
    # Соединяем инструкцию из файла prompts.py с текстом родителя
    final_prompt = ANALYSIS_PROMPT.format(text=text)
    try:
        response = model.generate_content(final_prompt)
        return response.text
    except Exception as e:
        return f"Ошибка при анализе: {e}"

# Поле для ввода
text_input = st.text_area("📄 Вставьте текст заключения или анализов:", height=200)

if st.button("🚀 Найти причину сбоя"):
    if not text_input:
        st.warning("⚠️ Пожалуйста, добавьте текст для анализа.")
    else:
        with st.spinner("⏳ ИИ анализирует биохимические цепочки..."):
            res = analyze_with_ai(text_input)
            st.success("Анализ завершен!")
            st.markdown("---")
            st.markdown(res)
