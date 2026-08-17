"""Downloads a speech model ahead of time, so the first real run is offline.

Called by setup.bat; can also be run by hand to fetch a different size:
    python\\python.exe download_model.py large-v3
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models", "whisper")

SIZES = {
    "large-v3": "~3 ГБ, максимальное качество",
    "distil-large-v3": "~1.5 ГБ, почти как large-v3, но быстрее",
    "medium": "~1.5 ГБ, баланс",
    "small": "~500 МБ, быстро",
    "base": "~150 МБ, черновой вариант",
    "tiny": "~75 МБ, для проверки",
}


def main():
    size = sys.argv[1] if len(sys.argv) > 1 else "large-v3"
    if size not in SIZES:
        print(f"Неизвестный размер модели: {size}")
        print("Доступны: " + ", ".join(SIZES))
        return 1

    os.makedirs(MODELS_DIR, exist_ok=True)
    print(f"Скачиваю модель {size} ({SIZES[size]})...")
    print(f"Папка: {MODELS_DIR}")
    print("Если загрузка оборвётся - запустите ещё раз, докачается с места обрыва.\n")

    try:
        from faster_whisper import WhisperModel
        # Loading is what pulls the files; CPU/int8 keeps it light, the model is
        # the same on disk whichever device runs it later.
        WhisperModel(size, device="cpu", compute_type="int8", download_root=MODELS_DIR)
    except Exception as e:
        print(f"\nНе получилось: {e}")
        return 1

    print(f"\nМодель {size} готова. Интернет для распознавания больше не нужен.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
