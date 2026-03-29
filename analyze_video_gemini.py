"""
Yasno — Video Analysis via Gemini
Запуск: python3 analyze_video.py Mansur1.mp4
"""

import sys
import os
import json
import time
import google.generativeai as genai

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
OUTPUT_FILE = "yasno_report.txt"

PROMPT = """
You are a behavioral observation specialist reviewing a home video for developmental documentation purposes.
The parent has consented to this analysis for educational and clinical preparation purposes.

Please analyze this video and provide structured observations about:

1. EYE CONTACT & GAZE
- Does the person make eye contact? How often and for how long?
- Do they follow others' gaze or pointing gestures?

2. MOTOR PATTERNS
- Hand movements, body posture, coordination
- Any repetitive movements — describe type and frequency

3. COMMUNICATION & SOUNDS
- Vocalizations — type, frequency, context
- Response to name or verbal cues if visible

4. SOCIAL ENGAGEMENT
- Awareness of others in the environment
- Initiation of interaction

5. ATTENTION & FOCUS
- What captures attention, how long maintained

For each observation provide:
- WHAT I SEE: specific description with approximate timestamp
- WHY IT MATTERS: developmental significance
- RESEARCH REFERENCE: relevant study or clinical guideline
- QUESTION FOR SPECIALIST: one specific question based on this observation

Also note:
- POSITIVE FINDINGS: strengths and capabilities observed
- PRIORITY: the single most important observation

End with:
DISCLAIMER: These are structured observational notes to support discussion with a qualified specialist. Yasno does not provide diagnoses and does not replace professional medical evaluation.

Be specific, objective, and compassionate in your language.
"""


def analyze_with_gemini(video_path: str, api_key: str) -> str:
    """Upload video to Gemini and analyze"""
    genai.configure(api_key=api_key)

    print("Загружаю видео в Gemini...")
    video_file = genai.upload_file(path=video_path)

    # Wait for processing
    print("Обрабатываю...")
    while video_file.state.name == "PROCESSING":
        time.sleep(3)
        video_file = genai.get_file(video_file.name)

    if video_file.state.name == "FAILED":
        raise ValueError("Gemini не смог обработать видео")

    print("Анализирую поведенческие паттерны...")

    model = genai.GenerativeModel("gemini-2.0-flash-001")
    response = model.generate_content(
        [video_file, PROMPT],
        generation_config={"temperature": 0.2, "max_output_tokens": 8000}
    )

    # Clean up uploaded file
    try:
        genai.delete_file(video_file.name)
    except:
        pass

    return response.text


def format_report(analysis_text: str, video_path: str) -> str:
    """Format the final report"""
    lines = []
    lines.append("=" * 60)
    lines.append("YASNO — ОТЧЁТ ПО ВИДЕОНАБЛЮДЕНИЮ")
    lines.append("=" * 60)
    lines.append(f"Файл: {os.path.basename(video_path)}")
    lines.append(f"Модель: Gemini 2.0 Flash Vision")
    lines.append("")
    lines.append(analysis_text)
    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Использование: python3 analyze_video.py video.mp4")
        sys.exit(1)

    video_path = sys.argv[1]

    if not os.path.exists(video_path):
        print(f"Файл не найден: {video_path}")
        sys.exit(1)

    api_key = GOOGLE_API_KEY
    if not api_key:
        api_key = input("Введите Google API ключ (AIza...): ").strip()

    if not api_key:
        print("Нужен Google API ключ")
        print("Получить: https://aistudio.google.com/app/apikey")
        sys.exit(1)

    print(f"\nАнализирую: {video_path}")
    print("-" * 40)

    try:
        analysis = analyze_with_gemini(video_path, api_key)
        report = format_report(analysis, video_path)

        print("\n" + report)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"\nОтчёт сохранён: {OUTPUT_FILE}")

    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
