"""Batch-first orchestration for Manual transcription, review and rendering."""

from __future__ import annotations

import copy
import json
import os
import threading
import uuid
from pathlib import Path

from lib.transcript_revisions import TranscriptStore


TRANSCRIPTION_ACTIVE = {"queued", "transcribing"}


class ManualJobError(RuntimeError):
    pass


class ManualJobService:
    def __init__(self, revisions_dir, transcribe_fn, render_fn, event_cb=None):
        self.store = TranscriptStore(revisions_dir)
        self.transcribe_fn = transcribe_fn
        self.render_fn = render_fn
        self.event_cb = event_cb
        self.jobs = {}
        self.item_to_job = {}
        self.lock = threading.RLock()
        self.jobs_path = Path(revisions_dir) / "manual_jobs.json"
        self._load_jobs()

    def _load_jobs(self):
        if not self.jobs_path.exists():
            return
        try:
            with self.jobs_path.open("r", encoding="utf-8") as handle:
                saved = json.load(handle)
            for job in saved.get("jobs", []):
                for item in job.get("items", []):
                    if item.get("state") in {"queued", "transcribing", "rendering"}:
                        item.update(
                            state="cancelled", stage="cancelled",
                            error="Работа была прервана при закрытии приложения",
                        )
                    self.item_to_job[item["item_id"]] = job["job_id"]
                self.jobs[job["job_id"]] = job
        except (OSError, ValueError, KeyError):
            self.jobs = {}
            self.item_to_job = {}

    def _persist_jobs(self):
        temp = self.jobs_path.with_suffix(".json.tmp")
        with temp.open("w", encoding="utf-8") as handle:
            json.dump({"jobs": list(self.jobs.values())}, handle, ensure_ascii=False, indent=2)
        os.replace(temp, self.jobs_path)

    def _emit(self, job, item=None, persist=True):
        if persist:
            self._persist_jobs()
        if self.event_cb:
            self.event_cb(self._snapshot_unlocked(job), copy.deepcopy(item) if item else None)

    def create_job(self, videos, params):
        with self.lock:
            job_id = "manual-" + uuid.uuid4().hex[:12]
            items = []
            for index, path in enumerate(videos):
                item_id = "item-" + uuid.uuid4().hex[:12]
                item = {
                    "item_id": item_id,
                    "index": index,
                    "path": os.path.abspath(os.fspath(path)),
                    "name": os.path.basename(os.fspath(path)),
                    "state": "queued",
                    "progress": 0,
                    "stage": "queued",
                    "error": None,
                    "revision": None,
                    "output": None,
                }
                items.append(item)
                self.item_to_job[item_id] = job_id
            job = {"job_id": job_id, "params": copy.deepcopy(params), "items": items}
            self.jobs[job_id] = job
            self._persist_jobs()
            return self._snapshot_unlocked(job)

    def _job(self, job_id):
        try:
            return self.jobs[job_id]
        except KeyError as exc:
            raise ManualJobError("job not found") from exc

    def _item(self, item_id):
        job = self._job(self.item_to_job.get(item_id))
        for item in job["items"]:
            if item["item_id"] == item_id:
                return job, item
        raise ManualJobError("item not found")

    def _snapshot_unlocked(self, job):
        items = copy.deepcopy(job["items"])
        settled = all(item["state"] not in TRANSCRIPTION_ACTIVE for item in items)
        approved = sum(item["state"] == "approved" for item in items)
        return {
            "job_id": job["job_id"],
            "items": items,
            "transcription_settled": settled,
            "approved_count": approved,
            "render_ready": settled and approved > 0,
        }

    def snapshot(self, job_id):
        with self.lock:
            return self._snapshot_unlocked(self._job(job_id))

    def latest_snapshot(self):
        with self.lock:
            if not self.jobs:
                return None
            return self._snapshot_unlocked(list(self.jobs.values())[-1])

    def run_transcription(self, job_id, cancelled=None, selected_ids=None):
        job = self._job(job_id)
        selected = set(selected_ids) if selected_ids is not None else None
        for item in job["items"]:
            if selected is not None and item["item_id"] not in selected:
                continue
            if item["state"] not in {"queued", "failed", "no_speech", "cancelled"}:
                continue
            if cancelled and cancelled():
                item.update(state="cancelled", stage="cancelled")
                self._emit(job, item)
                continue
            item.update(state="transcribing", stage="loading_model", progress=0, error=None)
            self._emit(job, item)

            def progress(stage, pct, current=item):
                current.update(stage=stage, progress=int(pct))
                self._emit(job, current, persist=False)

            try:
                effective_params = dict(job["params"])
                effective_params.update(item.pop("params_override", {}))
                artifact = self.transcribe_fn(
                    item["path"], progress_cb=progress, **effective_params
                )
                transcript = artifact["transcript"]
                revision = self.store.create(
                    item["item_id"], item["path"], transcript, effective_params
                )
                state = "transcribed" if revision["words"] else "no_speech"
                item.update(
                    state=state, stage=state, progress=100,
                    revision=revision["revision"], error=None,
                )
            except Exception as exc:
                item.update(state="failed", stage="failed", error=str(exc))
            self._emit(job, item)
        return self.snapshot(job_id)

    def retranscribe(self, item_id, params=None, cancelled=None):
        job, item = self._item(item_id)
        item.update(state="queued", stage="queued", progress=0, error=None, output=None)
        if params:
            item["params_override"] = copy.deepcopy(params)
        self._emit(job, item)
        return self.run_transcription(
            job["job_id"], selected_ids=[item_id], cancelled=cancelled
        )

    def get_transcript(self, item_id):
        self._item(item_id)
        return self.store.latest(item_id)

    def apply_patch(self, item_id, base_revision, operations):
        job, item = self._item(item_id)
        revision = self.store.apply_patch(item_id, base_revision, operations)
        item.update(state="needs_review", revision=revision["revision"], error=None)
        self._emit(job, item)
        return revision

    def approve(self, item_id, revision):
        job, item = self._item(item_id)
        approved = self.store.approve(item_id, revision)
        item.update(state="approved", revision=approved["revision"], error=None)
        self._emit(job, item)
        return approved

    def run_render(self, job_id, style, output_dir, selected_ids=None, cancelled=None):
        job = self._job(job_id)
        if not self._snapshot_unlocked(job)["transcription_settled"]:
            raise ManualJobError("transcription is still running")
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        selected = set(selected_ids or [item["item_id"] for item in job["items"]])
        completed = failed = skipped = 0
        used_names = set()
        for item in job["items"]:
            if item["item_id"] not in selected or item["state"] != "approved":
                skipped += 1
                continue
            if cancelled and cancelled():
                item.update(state="cancelled", stage="cancelled")
                skipped += 1
                self._emit(job, item)
                continue
            stem = Path(item["path"]).stem + "_captioned"
            candidate = stem
            suffix = 2
            while candidate.lower() in used_names or (output_dir / f"{candidate}.mp4").exists():
                candidate = f"{stem}_{suffix}"
                suffix += 1
            used_names.add(candidate.lower())
            output = output_dir / f"{candidate}.mp4"
            item.update(state="rendering", stage="preparing", progress=0, error=None)
            self._emit(job, item)

            def progress(stage, pct, current=item):
                current.update(stage=stage, progress=int(pct))
                self._emit(job, current, persist=False)

            try:
                segments = self.store.render_segments(item["item_id"], item["revision"])
                result = self.render_fn(
                    item["path"], output, segments, style=copy.deepcopy(style), progress_cb=progress
                )
                item.update(
                    state="completed", stage="completed", progress=100,
                    output=result["output"], error=None,
                )
                completed += 1
            except Exception as exc:
                item.update(state="render_failed", stage="render_failed", error=str(exc))
                failed += 1
            self._emit(job, item)
        return {"completed": completed, "failed": failed, "skipped": skipped}
