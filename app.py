"""
AISubs desktop app: pywebview window hosting gui/index.html, backed by a small
js_api bridge that drives transcribe.py + renderer.py (pipeline.py).
"""

import os
import sys
import json
import glob
import queue
import threading
import traceback
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import webview
from webview import FileDialog

import pipeline as pipeline_mod
import mediaserver
import fontlist
from lib.manual_jobs import ManualJobService
from lib.output_planner import plan_output_paths
from lib.transcript_revisions import RevisionConflict, TranscriptError, ValidationError

PRESETS_DIR = os.path.join(BASE_DIR, "presets")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
REVISIONS_DIR = os.path.join(BASE_DIR, "cache", "revisions")
os.makedirs(OUTPUT_DIR, exist_ok=True)

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv", ".flv", ".mpg", ".mpeg", ".ts"}


class Api:
    """Methods here are exposed to JS by pywebview.

    Attributes must stay underscore-private: pywebview walks the public
    attributes of this object to expose them, and a pywebview Window leads into
    the WinForms object graph, which recurses until it blows the stack.
    """

    def __init__(self):
        self._window = None
        self._cancelled = False
        self._js_queue = queue.Queue()
        self._js_thread = threading.Thread(target=self._js_pump, daemon=True)
        self._js_thread.start()
        self._manual = ManualJobService(
            REVISIONS_DIR,
            pipeline_mod.transcribe_phase,
            pipeline_mod.render_phase,
            event_cb=self._manual_event,
        )

    # ---------- presets ----------

    def list_presets(self):
        result = []
        for path in sorted(glob.glob(os.path.join(PRESETS_DIR, "*.json"))):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data.setdefault("name", os.path.splitext(os.path.basename(path))[0])
                data["filename"] = os.path.splitext(os.path.basename(path))[0]
                result.append(data)
            except Exception:
                continue
        return result

    def save_preset(self, name, style):
        safe = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip() or "custom"
        path = os.path.join(PRESETS_DIR, safe.replace(" ", "_") + ".json")
        style = dict(style)
        style["name"] = name
        with open(path, "w", encoding="utf-8") as f:
            json.dump(style, f, ensure_ascii=False, indent=2)
        return True

    # ---------- files ----------

    def pick_videos(self):
        """Opens the file dialog without blocking the js_api thread.

        WinForms' ShowDialog must run on the thread that owns the window; called
        straight from js_api it deadlocks and the window goes "not responding".
        So we hand it to the UI thread via BeginInvoke and deliver the result to
        JS through a callback instead of a return value.
        """
        form = getattr(self._window, "native", None)

        def show():
            try:
                result = self._window.create_file_dialog(
                    FileDialog.OPEN,
                    allow_multiple=True,
                    file_types=("Видео (*.mp4;*.mov;*.mkv;*.avi;*.webm)", "Все файлы (*.*)"),
                )
                self._push_files(list(result) if result else [])
            except Exception as e:
                traceback.print_exc()
                self._js("onPipelineError", f"Не удалось открыть диалог выбора файлов: {e}")

        if form is None:
            show()
        else:
            from System import Action
            form.BeginInvoke(Action(show))
        return True

    def _js_pump(self):
        """Serialises all JS calls onto one background thread.

        evaluate_js blocks until WebView2 answers, so calling it from the UI
        thread (drag & drop handlers run there) deadlocks the window. Queueing
        keeps callers non-blocking while preserving call order.
        """
        while True:
            script = self._js_queue.get()
            try:
                if self._window is not None:
                    self._window.evaluate_js(script)
            except Exception:
                pass

    def _js(self, fn, *js_args):
        payload = ", ".join(json.dumps(a, ensure_ascii=False) for a in js_args)
        self._js_queue.put(f"window.{fn}({payload})")

    def _push_files(self, paths):
        videos = [p for p in paths if os.path.splitext(p)[1].lower() in VIDEO_EXTS]
        self._js("onVideosPicked", videos)

    def _manual_event(self, snapshot, _item):
        self._js("onManualJobUpdated", snapshot)

    def delete_preset(self, filename):
        """Removes a preset by its file stem. Refuses anything that would
        escape the presets folder."""
        stem = os.path.basename(str(filename or "")).removesuffix(".json")
        if not stem or stem in (".", ".."):
            return {"ok": False, "error": "пустое имя"}

        path = os.path.join(PRESETS_DIR, stem + ".json")
        if os.path.dirname(os.path.abspath(path)) != os.path.abspath(PRESETS_DIR):
            return {"ok": False, "error": "недопустимый путь"}
        if not os.path.exists(path):
            return {"ok": False, "error": "пресет не найден"}

        try:
            os.remove(path)
            return {"ok": True}
        except Exception as e:
            traceback.print_exc()
            return {"ok": False, "error": str(e)}

    def models_status(self):
        """Which models are already on disk, so the UI can say what needs a download."""
        try:
            import transcribe as t
            models_dir = os.path.join(BASE_DIR, "models", "whisper")
            return {size: t.is_model_cached(size, models_dir) for size in
                    ("large-v3", "distil-large-v3", "medium", "small", "base", "tiny")}
        except Exception:
            traceback.print_exc()
            return {}

    def list_fonts(self):
        """Bundled faces plus everything installed in Windows."""
        try:
            return fontlist.list_fonts()
        except Exception:
            traceback.print_exc()
            return []

    def font_url(self, path):
        """URL of a font file, so the preview can @font-face it directly."""
        try:
            file_path = str(path).partition("#")[0]
            if not os.path.isabs(file_path):
                file_path = os.path.join(BASE_DIR, file_path)
            if not os.path.exists(file_path):
                return None
            return mediaserver.font_url(file_path)
        except Exception:
            traceback.print_exc()
            return None

    def video_info(self, path):
        """Geometry plus http URLs the page can actually load (file:// cannot).

        Frame extraction is the slow part, so it is requested separately.
        """
        try:
            info = mediaserver.probe(path)
            info["media_url"] = mediaserver.media_url(path)
            info["name"] = os.path.basename(path)
            return info
        except Exception:
            traceback.print_exc()
            return {}

    def frame_url(self, path, at_seconds=None):
        try:
            return mediaserver.frame_url(path, at_seconds)
        except Exception:
            traceback.print_exc()
            return None

    def open_output_folder(self, path):
        target = os.path.dirname(path) if path and os.path.isfile(path) else OUTPUT_DIR
        os.startfile(target)
        return True

    # ---------- system info ----------

    def get_gpu_info(self):
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5,
            )
            name = out.stdout.strip().splitlines()[0] if out.returncode == 0 and out.stdout.strip() else None
            return {"available": bool(name), "name": name}
        except Exception:
            return {"available": False, "name": None}

    # ---------- pipeline ----------

    def cancel_queue(self):
        self._cancelled = True
        return True

    def run_pipeline(self, args):
        videos = args.get("videos") or []
        style = args.get("style")
        model = args.get("model") or "large-v3"
        device = args.get("device") or "auto"
        language = args.get("language") or None

        self._cancelled = False
        output_paths = plan_output_paths(videos, OUTPUT_DIR)

        js = self._js

        def worker():
            outputs = []
            for index, video in enumerate(videos):
                if self._cancelled:
                    break

                output_path = output_paths[index]

                js("onFileStarted", index)
                try:
                    result = pipeline_mod.run_pipeline(
                        video,
                        output_path,
                        style=style,
                        model_size=model,
                        device=device,
                        language=language,
                        progress_cb=lambda stage, pct: js("updateProgress", stage, int(pct), index),
                    )
                    outputs.append(result["output"])
                    js("onFileDone", index, result["output"])
                except Exception as e:
                    traceback.print_exc()
                    js("onFileError", index, str(e))

            js("onQueueDone", outputs)

        threading.Thread(target=worker, daemon=True).start()
        return {"started": True, "count": len(videos)}

    def start_manual_job(self, args):
        videos = args.get("videos") or []
        if not videos:
            return {"ok": False, "error": "Добавьте хотя бы одно видео"}
        self._cancelled = False
        params = {
            "model_size": args.get("model") or "large-v3",
            "device": args.get("device") or "auto",
            "language": args.get("language") or None,
        }
        snapshot = self._manual.create_job(videos, params)

        def worker():
            result = self._manual.run_transcription(
                snapshot["job_id"], cancelled=lambda: self._cancelled
            )
            self._js("onManualJobUpdated", result)

        threading.Thread(target=worker, daemon=True).start()
        return {"ok": True, "job": snapshot}

    def get_manual_job(self, job_id):
        try:
            return {"ok": True, "job": self._manual.snapshot(job_id)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def latest_manual_job(self):
        try:
            return {"ok": True, "job": self._manual.latest_snapshot()}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def get_transcript(self, item_id):
        try:
            return {"ok": True, "transcript": self._manual.get_transcript(item_id)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def apply_transcript_patch(self, item_id, base_revision, operations):
        try:
            revision = self._manual.apply_patch(item_id, base_revision, operations or [])
            return {"ok": True, "transcript": revision}
        except RevisionConflict as exc:
            return {"ok": False, "code": "revision_conflict", "error": str(exc)}
        except TranscriptError as exc:
            return {"ok": False, "code": "invalid_patch", "error": str(exc)}
        except Exception as exc:
            traceback.print_exc()
            return {"ok": False, "code": "internal", "error": str(exc)}

    def approve_transcript(self, item_id, revision):
        try:
            approved = self._manual.approve(item_id, revision)
            return {"ok": True, "transcript": approved}
        except ValidationError as exc:
            return {"ok": False, "code": "validation", "errors": exc.errors, "error": str(exc)}
        except RevisionConflict as exc:
            return {"ok": False, "code": "revision_conflict", "error": str(exc)}
        except Exception as exc:
            return {"ok": False, "code": "internal", "error": str(exc)}

    def approve_clean_transcripts(self, job_id):
        try:
            snapshot = self._manual.snapshot(job_id)
            approved = []
            rejected = []
            for item in snapshot["items"]:
                if item["state"] not in {"transcribed", "needs_review"}:
                    continue
                transcript = self._manual.get_transcript(item["item_id"])
                errors = self._manual.store.validation_errors(transcript)
                low_confidence = any(
                    word.get("probability") is not None and word["probability"] < 0.65
                    for word in transcript["words"] if not word.get("deleted")
                )
                if errors or low_confidence:
                    rejected.append(item["item_id"])
                    continue
                self._manual.approve(item["item_id"], transcript["revision"])
                approved.append(item["item_id"])
            return {"ok": True, "approved": approved, "needs_attention": rejected}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def retry_manual_transcription(self, job_id, item_ids=None):
        try:
            snapshot = self._manual.snapshot(job_id)
            selected = item_ids or [
                item["item_id"] for item in snapshot["items"]
                if item["state"] in {"failed", "no_speech", "cancelled"}
            ]
            if not selected:
                return {"ok": False, "error": "Нет файлов для повтора"}
            self._cancelled = False
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        def worker():
            result = self._manual.run_transcription(
                job_id, selected_ids=selected, cancelled=lambda: self._cancelled
            )
            self._js("onManualJobUpdated", result)

        threading.Thread(target=worker, daemon=True).start()
        return {"ok": True, "count": len(selected)}

    def retranscribe_manual_item(self, item_id, args=None):
        args = args or {}
        params = {
            "model_size": args.get("model") or "large-v3",
            "device": args.get("device") or "auto",
            "language": args.get("language") or None,
            "use_cached_transcript": False,
        }
        self._cancelled = False

        def worker():
            try:
                snapshot = self._manual.retranscribe(
                    item_id, params=params, cancelled=lambda: self._cancelled
                )
                self._js("onManualJobUpdated", snapshot)
            except Exception as exc:
                traceback.print_exc()
                self._js("onPipelineError", f"Повторная транскрибация: {exc}")

        threading.Thread(target=worker, daemon=True).start()
        return {"ok": True, "started": True}

    def start_manual_render(self, args):
        job_id = args.get("job_id")
        style = args.get("style") or {}
        selected_ids = args.get("item_ids") or None
        self._cancelled = False
        try:
            snapshot = self._manual.snapshot(job_id)
            if not snapshot["render_ready"]:
                return {"ok": False, "error": "Дождитесь транскрибации и одобрите хотя бы один файл"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        def worker():
            result = self._manual.run_render(
                job_id, style, OUTPUT_DIR, selected_ids=selected_ids,
                cancelled=lambda: self._cancelled,
            )
            self._js("onManualRenderDone", job_id, result)
            self._js("onManualJobUpdated", self._manual.snapshot(job_id))

        threading.Thread(target=worker, daemon=True).start()
        return {"ok": True, "started": True}


def enable_file_drop(api, window):
    """Native drag & drop of video files.

    The HTML5 File API never exposes a real path, so dropping onto the page is
    useless for us. Instead WebView2's own drop handling is switched off and the
    hosting WinForms window takes the drop, which does carry full paths.

    All of this must run on the UI thread - WebView2 controller properties throw
    if touched from anywhere else.
    """
    form = getattr(window, "native", None)
    if form is None:
        return

    from System import Action

    def setup():
        _setup_file_drop(api, form)

    try:
        form.BeginInvoke(Action(setup))
    except Exception:
        traceback.print_exc()


def _setup_file_drop(api, form):
    try:
        from System.Windows.Forms import DragDropEffects, DataFormats

        webview_control = getattr(form, "webview", None)
        if webview_control is not None:
            try:
                webview_control.AllowExternalDrop = False
            except Exception:
                pass  # older WebView2 control: page-level drop simply stays inert

        def dropped_videos(args):
            if not args.Data.GetDataPresent(DataFormats.FileDrop):
                return []
            paths = list(args.Data.GetData(DataFormats.FileDrop))
            return [p for p in paths if os.path.splitext(p)[1].lower() in VIDEO_EXTS]

        # DragDropEffects.None is unreachable by attribute access ("None" is a
        # Python keyword), so it has to be fetched by name.
        effect_none = getattr(DragDropEffects, "None")

        def on_drag_enter(sender, args):
            if dropped_videos(args):
                args.Effect = DragDropEffects.Copy
                api._js("onDragEnter")
            else:
                args.Effect = effect_none

        def on_drag_leave(sender, args):
            api._js("onDragLeave")

        def on_drag_drop(sender, args):
            api._js("onDragLeave")
            videos = dropped_videos(args)
            if videos:
                api._js("onVideosPicked", videos)

        # Subscribe on the form AND on the WebView2 control. The control covers
        # the whole client area, so a drop lands on it first; relying on OLE to
        # walk up to the form is fragile because WebView2's inner windows live
        # in another process.
        targets = [form]
        if webview_control is not None:
            targets.append(webview_control)

        for target in targets:
            try:
                target.AllowDrop = True
                target.DragEnter += on_drag_enter
                target.DragLeave += on_drag_leave
                target.DragDrop += on_drag_drop
            except Exception:
                traceback.print_exc()

        # keep the delegates alive; .NET only holds weak refs through pythonnet
        api._drop_handlers = (on_drag_enter, on_drag_leave, on_drag_drop)
    except Exception:
        traceback.print_exc()


def main():
    mediaserver.start()
    api = Api()
    window = webview.create_window(
        "AISubs",
        os.path.join(BASE_DIR, "gui", "index.html"),
        js_api=api,
        width=1360,
        height=860,
        min_size=(1100, 700),
        background_color="#0c0e13",
    )
    # Must stay underscore-private: pywebview walks public attributes of js_api
    # to build the JS bridge, and a Window leads into the WinForms/.NET graph,
    # where a property read blocks on the UI thread and freezes the app.
    api._window = window
    window.events.shown += lambda: enable_file_drop(api, window)
    webview.start()


if __name__ == "__main__":
    main()
