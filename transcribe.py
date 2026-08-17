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


def enable_bundled_cuda_libs():
    """Makes pip-installed CUDA libraries findable.

    ctranslate2 loads cuBLAS by name at runtime. The pip packages put it in
    site-packages/nvidia/<lib>/bin, which is not on the DLL search path, so
    without this the GPU path fails and transcription quietly drops to CPU on
    any machine that lacks a system-wide CUDA Toolkit.
    """
    if os.name != "nt" or not hasattr(os, "add_dll_directory"):
        return []

    roots = []
    for base in {os.path.dirname(os.path.dirname(os.__file__)),
                 os.path.join(os.path.dirname(sys.executable), "Lib")}:
        nvidia = os.path.join(base, "site-packages", "nvidia")
        if os.path.isdir(nvidia):
            roots.append(nvidia)

    added = []
    for nvidia in roots:
        for lib in os.listdir(nvidia):
            bin_dir = os.path.join(nvidia, lib, "bin")
            if os.path.isdir(bin_dir):
                try:
                    os.add_dll_directory(bin_dir)
                    added.append(bin_dir)
                except OSError:
                    pass
    return added


enable_bundled_cuda_libs()


def repo_for(model_size):
    """Hugging Face repository backing a model name, or None for a local path."""
    try:
        from faster_whisper.utils import _MODELS
        return _MODELS.get(model_size)
    except Exception:
        return None


def is_model_cached(model_size, models_dir):
    """True when the model is already on disk, so no download will happen."""
    repo = repo_for(model_size)
    if not repo:
        return os.path.isdir(model_size)
    folder = os.path.join(models_dir, "models--" + repo.replace("/", "--"))
    if not os.path.isdir(folder):
        return False
    snapshots = os.path.join(folder, "snapshots")
    if not os.path.isdir(snapshots):
        return False

    # Judge by the model files themselves. Leftover *.incomplete blobs from an
    # interrupted attempt can sit next to a perfectly complete model, so their
    # presence says nothing about whether it is usable.
    for entry in os.scandir(snapshots):
        if not entry.is_dir():
            continue
        names = os.listdir(entry.path)
        if "model.bin" in names and "config.json" in names:
            return True
    return False


def _download_with_progress(model_size, models_dir, progress_cb, log=print):
    """Fetches the model up front so the UI can show real download progress.

    WhisperModel would download silently on first use, which looks like a
    freeze when a 3 GB model is picked.
    """
    repo = repo_for(model_size)
    if not repo:
        return

    import threading

    # The xet backend stages downloads in its own global scratch area and only
    # materialises files at the very end, so the cache stays empty and progress
    # would sit at 0% for minutes. The classic backend writes as it goes.
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

    from huggingface_hub import snapshot_download
    import huggingface_hub

    total = 0
    try:
        info = huggingface_hub.HfApi().model_info(repo, files_metadata=True)
        total = sum(s.size or 0 for s in (info.siblings or []))
    except Exception:
        pass  # size unknown: the UI then just shows the stage without a number

    log(f"[transcribe] downloading {model_size} ({total/1e9:.1f} GB)" if total
        else f"[transcribe] downloading {model_size}")

    # Progress is measured from how much the cache grows, not from the library's
    # progress bars: downloads can go through a backend that reports nothing
    # until a file is complete, and it stages data in its own scratch area, so
    # watching one folder or the bars alone shows a frozen 0% on a large model.
    def cache_bytes():
        got = 0
        for root, _, files in os.walk(models_dir):
            for f in files:
                try:
                    got += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
        return got

    baseline = cache_bytes()
    stop = threading.Event()

    def watch():
        while not stop.wait(0.5):
            if not (progress_cb and total):
                continue
            grown = max(0, cache_bytes() - baseline)
            progress_cb("downloading_model", min(int(100 * grown / total), 99))

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    try:
        snapshot_download(repo, cache_dir=models_dir)
    finally:
        stop.set()
        watcher.join(timeout=2)

    if progress_cb:
        progress_cb("downloading_model", 100)


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

    # Download first, with progress, instead of letting the model loader do it
    # silently - a 3 GB fetch behind a static "loading" label reads as a hang.
    if not is_model_cached(model_size, models_dir):
        try:
            _download_with_progress(model_size, models_dir, progress_cb)
        except Exception as e:
            print(f"[transcribe] pre-download failed ({e}), falling back to loader")

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
