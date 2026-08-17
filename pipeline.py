"""Glue: transcribe (cached) + render in one call. Used by both the GUI and CLI use."""

import os
import json
import sys
import hashlib

sys.path.insert(0, os.path.dirname(__file__))
import transcribe as transcribe_mod
import renderer as renderer_mod

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")

def words_json_path_for(video_path):
    """Transcripts live in AISubs/cache, not next to the user's source video.
    The path hash keeps same-named files from different folders apart."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    full = os.path.abspath(video_path)
    digest = hashlib.sha1(full.encode("utf-8")).hexdigest()[:8]
    base = os.path.splitext(os.path.basename(full))[0]
    return os.path.join(CACHE_DIR, f"{base}_{digest}.words.json")

def run_pipeline(
    video_path,
    output_path,
    style=None,
    preset_path=None,
    model_size="large-v3",
    device="auto",
    language=None,
    use_cached_transcript=True,
    progress_cb=None,
):
    if preset_path:
        with open(preset_path, "r", encoding="utf-8") as f:
            style = json.load(f)

    words_path = words_json_path_for(video_path)
    if use_cached_transcript and os.path.exists(words_path):
        with open(words_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if progress_cb:
            progress_cb("transcribing", 100)
    else:
        data = transcribe_mod.transcribe(
            video_path,
            model_size=model_size,
            device=device,
            language=language,
            progress_cb=progress_cb,
        )
        with open(words_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    renderer_mod.render_captions(video_path, data["segments"], output_path, style=style, progress_cb=progress_cb)
    return {"output": output_path, "words_json": words_path, "language": data.get("language"), "device": data.get("device")}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("output")
    parser.add_argument("--preset", default=os.path.join(os.path.dirname(__file__), "presets", "vk_blue_pill.json"))
    parser.add_argument("--model", default="large-v3")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--language", default=None)
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    result = run_pipeline(
        args.video,
        args.output,
        preset_path=args.preset,
        model_size=args.model,
        device=args.device,
        language=args.language,
        use_cached_transcript=not args.no_cache,
        progress_cb=lambda stage, pct: print(f"[{stage}] {pct}%"),
    )
    print("Done:", result)
