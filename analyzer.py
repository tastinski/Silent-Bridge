import streamlit as st
import google.generativeai as genai

# --- НАСТРОЙКИ (Твой ключ) ---
GOOGLE_API_KEY = "ВСТАВЬ_СЮДА_СВОЙ_КЛЮЧ"
genai.configure(api_key=GOOGLE_API_KEY)

# --- УМНЫЙ БЛОК: АВТО-ПОИСК МОДЕЛИ ---
# Мы не гадаем название, мы спрашиваем у Google, что доступно для твоего ключа
def get_best_model():
    try:
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        # 1. Пытаемся найти самую быструю (Flash)
        flash_model = next((m for m in available_models if 'flash' in m and '1.5' in m), None)
        if flash_model: return flash_model
        
        # 2. Если нет Flash 1.5, ищем любую Flash
        any_flash = next((m for m in available_models if 'flash' in m), None)
        if any_flash: return any_flash
        
        # 3. Если нет Flash, берем стандартную Pro
        pro_model = next((m for m in available_models if 'pro' in m), None)
        if pro_model: return pro_model
        
        # 4. Если вообще ничего не понятно, берем первую попавшуюся
        return available_models[0] if available_models else "gemini-pro"
        
    except Exception as e:
        # Если совсем беда, возвращаем старую надежную классику
        return "gemini-pro"

# Получаем рабочую модель
MODEL_NAME = get_best_model()
model = genai.GenerativeModel(MODEL_NAME)

# --- ИНТЕРФЕЙС ---
st.set_page_config(page_title="Silent Bridge AI", page_icon="🌉")
st.title("🌉 Silent Bridge: AI Analytics")

# Показываем, какая модель сейчас работает (для твоего спокойствия)
st.caption(f"🚀 Подключен мозг: **{MODEL_NAME}**")

def analyze_with_ai(text):
    prompt = f"""
    Ты - опытный медицинский аналитик (РАС, неврология).
    Проанализируй выписку для родителя:
    "{text}"
    
    Дай ответ по пунктам:
    1. 📋 **Диагнозы** (простыми словами).
    2. 💊 **Лекарства** (группы препаратов).
    3. ⚠️ **Важное** (риски, эффективность).
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Ошибка ({MODEL_NAME}): {e}"

text_input = st.text_area("Вставь текст заключения:", height=250)

if st.button("🚀 Запустить Анализ"):
    if not text_input:
        st.warning("Сначала вставь текст!")
    else:
        with st.spinner(f"ИИ ({MODEL_NAME}) читает документ..."):
            res = analyze_with_ai(text_input)
            st.markdown("---")
            st.markdown(res)
