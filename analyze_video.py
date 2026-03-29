"""
Yasno — Video Analysis
Запуск: python3 analyze_video.py video.mp4
"""

import sys
import os
import base64
import cv2
import json
from openai import OpenAI

# ─── CONFIG ───────────────────────────────────────
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
FRAMES_TO_EXTRACT = 12  # Сколько кадров берём из видео
OUTPUT_FILE = "yasno_report.txt"

SYSTEM_PROMPT = """
You are a behavioral research analyst specializing in developmental observation.
You analyze video frames and document observable behavioral patterns for clinical review purposes.

This is a parent-consented developmental observation session for educational documentation.

YOUR TASK:
Analyze the provided video frames and describe observable behavioral patterns objectively.

OBSERVATION AREAS:
- Eye contact and gaze patterns - frequency, duration, context
- Motor patterns - hand movements, body posture, coordination
- Repetitive movements - type, frequency, context
- Environmental responses - reactions to surroundings
- Vocalizations - if audible
- Joint attention - following gaze or gesture

RULES:
1. Describe only what is visible - no assumptions
2. Do NOT diagnose
3. Support each observation with a research reference
4. Write clearly for a parent audience

ФОРМАТ ОТВЕТА — СТРОГО JSON:
{
  "observations": [
    {
      "category": "название категории (например: Зрительный контакт)",
      "what_i_see": "конкретное описание что видно на кадрах",
      "significance": "почему это важно с точки зрения развития",
      "pubmed_ref": "название исследования или рекомендации + год",
      "question_for_doctor": "конкретный вопрос для специалиста"
    }
  ],
  "positive_findings": "что хорошего видно — обязательно найти",
  "priority_observation": "самое важное наблюдение одним предложением",
  "disclaimer": "Это структурированные наблюдения для обсуждения со специалистом. Yasno не ставит диагнозы и не заменяет врача."
}

Отвечай ТОЛЬКО валидным JSON. Никакого другого текста.
"""


def extract_frames(video_path: str, num_frames: int = 12) -> list:
    """Извлекает кадры из видео равномерно"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Не могу открыть видео: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration = total_frames / fps if fps > 0 else 0

    print(f"Видео: {duration:.1f} сек, {total_frames} кадров, {fps:.1f} fps")

    # Равномерно берём кадры
    indices = [int(i * total_frames / num_frames) for i in range(num_frames)]

    frames = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if ret:
            # Конвертируем в JPEG base64
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            b64 = base64.b64encode(buffer).decode('utf-8')
            timestamp = idx / fps if fps > 0 else 0
            frames.append({
                "b64": b64,
                "timestamp": timestamp,
                "frame_idx": idx
            })

    cap.release()
    print(f"Извлечено {len(frames)} кадров")
    return frames


def analyze_frames(client: OpenAI, frames: list) -> dict:
    """Отправляет кадры в GPT-4o Vision"""

    # Строим сообщение с кадрами
    content = []

    content.append({
        "type": "text",
        "text": f"Я предоставляю {len(frames)} кадров из видео ребёнка. Кадры сделаны равномерно на протяжении всего видео. Проанализируй поведенческие паттерны."
    })

    for i, frame in enumerate(frames):
        # Добавляем временную метку
        content.append({
            "type": "text",
            "text": f"Кадр {i+1} (время: {frame['timestamp']:.1f} сек):"
        })
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{frame['b64']}",
                "detail": "low"  # low = дешевле, high = точнее
            }
        })

    print("Отправляю в GPT-4o Vision...")

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content}
        ],
        max_tokens=2000,
        temperature=0.2
    )

    raw = response.choices[0].message.content

    # Парсим JSON
    try:
        # Убираем возможные markdown блоки
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        return json.loads(clean)
    except json.JSONDecodeError:
        # Если не JSON — возвращаем как текст
        return {"raw_response": raw, "error": "Не удалось распарсить JSON"}


def format_report(analysis: dict, video_path: str) -> str:
    """Форматирует красивый текстовый отчёт"""

    lines = []
    lines.append("=" * 60)
    lines.append("YASNO — ОТЧЁТ ПО ВИДЕОНАБЛЮДЕНИЮ")
    lines.append("=" * 60)
    lines.append(f"Файл: {os.path.basename(video_path)}")
    lines.append("")

    if "error" in analysis:
        lines.append("ОШИБКА АНАЛИЗА:")
        lines.append(analysis.get("raw_response", "Неизвестная ошибка"))
        return "\n".join(lines)

    # Главное наблюдение
    if "priority_observation" in analysis:
        lines.append("🎯 ГЛАВНОЕ НАБЛЮДЕНИЕ:")
        lines.append(f"   {analysis['priority_observation']}")
        lines.append("")

    # Позитивные находки
    if "positive_findings" in analysis:
        lines.append("✅ ЧТО ХОРОШЕГО:")
        lines.append(f"   {analysis['positive_findings']}")
        lines.append("")

    # Все наблюдения
    observations = analysis.get("observations", [])
    if observations:
        lines.append("📋 ПОДРОБНЫЕ НАБЛЮДЕНИЯ:")
        lines.append("-" * 40)

        for i, obs in enumerate(observations, 1):
            lines.append(f"\n{i}. {obs.get('category', 'Наблюдение').upper()}")
            lines.append(f"   Что вижу: {obs.get('what_i_see', '')}")
            lines.append(f"   Значимость: {obs.get('significance', '')}")
            lines.append(f"   Источник: {obs.get('pubmed_ref', '')}")
            lines.append(f"   ❓ Вопрос врачу: {obs.get('question_for_doctor', '')}")

    lines.append("")
    lines.append("=" * 60)
    lines.append("⚠️  ДИСКЛЕЙМЕР:")
    lines.append(analysis.get("disclaimer", "Yasno не является медицинским сервисом."))
    lines.append("=" * 60)

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Использование: python3 analyze_video.py путь/к/видео.mp4")
        print("Пример: python3 analyze_video.py mansur.mp4")
        sys.exit(1)

    video_path = sys.argv[1]

    if not os.path.exists(video_path):
        print(f"Файл не найден: {video_path}")
        sys.exit(1)

    # API ключ
    api_key = OPENAI_API_KEY
    if not api_key:
        api_key = input("Введите OpenAI API ключ: ").strip()

    if not api_key:
        print("Нужен API ключ")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    print(f"\nАнализирую: {video_path}")
    print("-" * 40)

    # Шаг 1 — Извлечь кадры
    try:
        frames = extract_frames(video_path, FRAMES_TO_EXTRACT)
    except Exception as e:
        print(f"Ошибка при чтении видео: {e}")
        print("Убедитесь что opencv установлен: pip install opencv-python")
        sys.exit(1)

    # Шаг 2 — Анализ
    try:
        analysis = analyze_frames(client, frames)
    except Exception as e:
        print(f"Ошибка API: {e}")
        sys.exit(1)

    # Шаг 3 — Отчёт
    report = format_report(analysis, video_path)

    print("\n" + report)

    # Сохраняем файл
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nОтчёт сохранён: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
