"""
Word-level transcription using faster-whisper, with automatic GPU->CPU fallback.
Produces a JSON file with captacity-style segments (segment.words[].{word,start,end})
that renderer.py consumes. Decoupled from rendering so re-styling doesn't require
re-transcribing.
"""

import os
import sys
import json
import argparse
import time

def _load_model(model_size, device, compute_type, download_root):
    from faster_whisper import WhisperModel
    return WhisperModel(model_size, device=device, compute_type=compute_type, download_root=download_root)

def load_model_with_fallback(model_size="large-v3", download_root=None, prefer_device="auto", log=print):
    attempts = []
    if prefer_device in ("auto", "cuda"):
        attempts.append(("cuda", "float16"))
    if prefer_device in ("auto", "cpu"):
        attempts.append(("cpu", "int8"))

    last_err = None
    for device, compute_type in attempts:
        try:
            model = _load_model(model_size, device, compute_type, download_root)
            log(f"[transcribe] using device={device} compute_type={compute_type}")
            return model, device, compute_type
        except Exception as e:
            last_err = e
            log(f"[transcribe] device={device} failed ({e}), trying next option...")
    raise RuntimeError(f"Could not load whisper model on any device: {last_err}")

def transcribe(
    input_path,
    model_size="large-v3",
    device="auto",
    language=None,
    initial_prompt=None,
    models_dir=None,
    progress_cb=None,
):
    if models_dir is None:
        models_dir = os.path.join(os.path.dirname(__file__), "models", "whisper")
    os.makedirs(models_dir, exist_ok=True)

    if progress_cb:
        progress_cb("loading_model", 0)

    model, used_device, compute_type = load_model_with_fallback(
        model_size=model_size, download_root=models_dir, prefer_device=device
    )

    if progress_cb:
        progress_cb("transcribing", 0)

    segments_iter, info = model.transcribe(
        input_path,
        word_timestamps=True,
        language=language,
        initial_prompt=initial_prompt,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=400),
    )

    duration = info.duration or 0
    segments = []
    for seg in segments_iter:
        words = []
        for w in (seg.words or []):
            words.append({"word": w.word, "start": w.start, "end": w.end, "probability": w.probability})
        if not words:
            continue
        segments.append({"start": seg.start, "end": seg.end, "text": seg.text, "words": words})

        if progress_cb and duration:
            progress_cb("transcribing", min(99, int(100 * seg.end / duration)))

    if progress_cb:
        progress_cb("transcribing", 100)

    return {
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": duration,
        "model": model_size,
        "device": used_device,
        "compute_type": compute_type,
        "segments": segments,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="video or audio file")
    parser.add_argument("-o", "--out", default=None, help="output JSON path")
    parser.add_argument("--model", default="large-v3")
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    parser.add_argument("--language", default=None, help="e.g. ru, en - omit for auto-detect")
    args = parser.parse_args()

    out_path = args.out or os.path.splitext(args.input)[0] + ".words.json"

    t0 = time.time()
    result = transcribe(
        args.input,
        model_size=args.model,
        device=args.device,
        language=args.language,
        progress_cb=lambda stage, pct: print(f"[{stage}] {pct}%"),
    )
    result["source_file"] = os.path.abspath(args.input)
    result["elapsed_seconds"] = time.time() - t0

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Detected language: {result['language']} (p={result['language_probability']:.2f})")
    print(f"Device: {result['device']}/{result['compute_type']}")
    print(f"Wrote {out_path} in {result['elapsed_seconds']:.1f}s")

if __name__ == "__main__":
    main()
