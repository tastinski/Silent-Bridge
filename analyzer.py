import streamlit as st
import google.generativeai as genai
from prompts import ANALYSIS_PROMPT  # Импорт твоего нового крутого промпта

# --- 1. АВТОРИЗАЦИЯ ---
if "GOOGLE_API_KEY" in st.secrets:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
else:
    GOOGLE_API_KEY = st.text_input("🔐 Введи свой Google API Key:", type="password")

if not GOOGLE_API_KEY:
    st.info("👈 Введи ключ, чтобы запустить систему.")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)

# --- 2. НАСТРОЙКА МОДЕЛИ ---
def get_best_model():
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        flash = next((m for m in models if 'flash' in m), None)
        return flash if flash else (models[0] if models else "gemini-pro")
    except:
        return "gemini-pro"

MODEL_NAME = get_best_model()
model = genai.GenerativeModel(MODEL_NAME)

# --- 3. ИНТЕРФЕЙС ---
st.set_page_config(page_title="Silent Bridge AI", page_icon="🌉")
st.title("🌉 Silent Bridge: AI Analytics")
st.caption(f"🚀 Система активна. Модель: **{MODEL_NAME}**")

def analyze_with_ai(text):
    final_prompt = ANALYSIS_PROMPT.format(text=text)
    
    # 🔥 БЛОК БЕССТРАШИЯ: Отключаем ложные срабатывания фильтров
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]
    
    try:
        # Передаем настройки безопасности
        response = model.generate_content(final_prompt, safety_settings=safety_settings)
        return response.text
    except Exception as e:
        return f"⚠️ Ошибка анализа: {e}"

# Поле ввода
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
