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

PRESETS_DIR = os.path.join(BASE_DIR, "presets")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
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

        js = self._js

        def worker():
            outputs = []
            for index, video in enumerate(videos):
                if self._cancelled:
                    break

                base = os.path.splitext(os.path.basename(video))[0]
                output_path = os.path.join(OUTPUT_DIR, f"{base}_captioned.mp4")

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
