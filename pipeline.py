"""Glue: transcribe (cached) + render in one call. Used by both the GUI and CLI use."""

import os
import json
import sys
import hashlib

sys.path.insert(0, os.path.dirname(__file__))
import transcribe as transcribe_mod
import renderer as renderer_mod

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")

def transcript_cache_path(video_path, model_size="large-v3", language=None, cache_dir=CACHE_DIR):
    """Return a cache path tied to source version and transcription inputs."""
    os.makedirs(cache_dir, exist_ok=True)
    full = os.path.abspath(os.fspath(video_path))
    stat = os.stat(full)
    identity = json.dumps({
        "path": full,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "model": model_size,
        "language": language or "auto",
    }, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:12]
    base = os.path.splitext(os.path.basename(full))[0]
    return os.path.join(os.fspath(cache_dir), f"{base}_{digest}.words.json")


def words_json_path_for(video_path):
    """Compatibility helper for callers that use default transcription inputs."""
    return transcript_cache_path(video_path)


def transcribe_phase(
    video_path,
    model_size="large-v3",
    device="auto",
    language=None,
    use_cached_transcript=True,
    progress_cb=None,
    cache_dir=CACHE_DIR,
):
    video_path = os.fspath(video_path)
    words_path = transcript_cache_path(video_path, model_size, language, cache_dir)
    if use_cached_transcript and os.path.exists(words_path):
        with open(words_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if progress_cb:
            progress_cb("transcribing", 100)
        cached = True
    else:
        data = transcribe_mod.transcribe(
            video_path,
            model_size=model_size,
            device=device,
            language=language,
            progress_cb=progress_cb,
        )
        temp_path = words_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(temp_path, words_path)
        cached = False
    return {
        "transcript": data,
        "words_json": words_path,
        "language": data.get("language"),
        "device": data.get("device"),
        "cached": cached,
    }


def render_phase(video_path, output_path, segments, style=None, progress_cb=None):
    video_path = os.fspath(video_path)
    output_path = os.fspath(output_path)
    if not segments or not any(segment.get("words") for segment in segments):
        raise ValueError("no speech was detected; video was not rendered")
    renderer_mod.render_captions(
        video_path, segments, output_path, style=style, progress_cb=progress_cb
    )
    return {"output": output_path}

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

    artifact = transcribe_phase(
        video_path,
        model_size=model_size,
        device=device,
        language=language,
        use_cached_transcript=use_cached_transcript,
        progress_cb=progress_cb,
    )
    result = render_phase(
        video_path, output_path, artifact["transcript"]["segments"],
        style=style, progress_cb=progress_cb,
    )
    result.update({
        "words_json": artifact["words_json"],
        "language": artifact["language"],
        "device": artifact["device"],
    })
    return result


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
