"""Persistent word-level transcript revisions used by Manual mode."""

from __future__ import annotations

import copy
import json
import os
import uuid
from pathlib import Path


class TranscriptError(ValueError):
    pass


class RevisionConflict(TranscriptError):
    pass


class ValidationError(TranscriptError):
    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


class TranscriptStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, item_id):
        safe = "".join(c for c in str(item_id) if c.isalnum() or c in "-_")
        if not safe:
            raise TranscriptError("invalid item id")
        return self.root / f"{safe}.revisions.json"

    def _load(self, item_id):
        path = self._path(item_id)
        if not path.exists():
            raise TranscriptError("transcript not found")
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _save(self, item_id, document):
        path = self._path(item_id)
        temp = path.with_suffix(path.suffix + ".tmp")
        with temp.open("w", encoding="utf-8") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=2)
        os.replace(temp, path)

    def create(self, item_id, source_path, transcription, params):
        words = []
        for segment_index, segment in enumerate(transcription.get("segments") or []):
            for word_index, word in enumerate(segment.get("words") or []):
                words.append({
                    "id": f"s{segment_index}-w{word_index}-{uuid.uuid4().hex[:8]}",
                    "word": word.get("word", ""),
                    "start": float(word.get("start", 0)),
                    "end": float(word.get("end", 0)),
                    "probability": word.get("probability"),
                    "segment_index": segment_index,
                    "edited": False,
                    "deleted": False,
                })
        path = self._path(item_id)
        document = self._load(item_id) if path.exists() else {"item_id": item_id, "revisions": []}
        revision = {
            "revision": document["revisions"][-1]["revision"] + 1 if document["revisions"] else 1,
            "status": "original",
            "source_path": os.path.abspath(source_path),
            "params": copy.deepcopy(params),
            "language": transcription.get("language"),
            "duration": float(transcription.get("duration") or 0),
            "words": words,
        }
        document["revisions"].append(revision)
        self._save(item_id, document)
        return copy.deepcopy(revision)

    def latest(self, item_id):
        return copy.deepcopy(self._load(item_id)["revisions"][-1])

    def get_revision(self, item_id, revision):
        for candidate in self._load(item_id)["revisions"]:
            if candidate["revision"] == int(revision):
                return copy.deepcopy(candidate)
        raise TranscriptError("revision not found")

    def apply_patch(self, item_id, base_revision, operations):
        document = self._load(item_id)
        current = document["revisions"][-1]
        if current["revision"] != int(base_revision):
            raise RevisionConflict(
                f"expected revision {current['revision']}, got {base_revision}"
            )

        draft = copy.deepcopy(current)
        draft["revision"] = current["revision"] + 1
        draft["status"] = "needs_review"
        by_id = {word["id"]: word for word in draft["words"]}
        for operation in operations:
            kind = operation.get("op")
            word = by_id.get(operation.get("word_id"))
            if kind in {"replace", "delete", "restore", "set_timing", "insert_after"} and word is None:
                raise TranscriptError("word not found")
            if kind == "replace":
                text = str(operation.get("text", ""))
                if not text.strip():
                    raise TranscriptError("word text cannot be empty")
                word["word"] = text
                word["edited"] = True
            elif kind == "delete":
                word["deleted"] = True
                word["edited"] = True
            elif kind == "restore":
                word["deleted"] = False
                word["edited"] = True
            elif kind == "set_timing":
                word["start"] = float(operation["start"])
                word["end"] = float(operation["end"])
                word["edited"] = True
            elif kind == "insert_after":
                inserted = {
                    "id": f"inserted-{uuid.uuid4().hex[:12]}",
                    "word": str(operation.get("text", "")),
                    "start": float(operation["start"]),
                    "end": float(operation["end"]),
                    "probability": None,
                    "segment_index": word["segment_index"],
                    "edited": True,
                    "deleted": False,
                }
                if not inserted["word"].strip():
                    raise TranscriptError("word text cannot be empty")
                index = draft["words"].index(word) + 1
                draft["words"].insert(index, inserted)
                by_id[inserted["id"]] = inserted
            else:
                raise TranscriptError(f"unsupported operation: {kind}")

        document["revisions"].append(draft)
        self._save(item_id, document)
        return copy.deepcopy(draft)

    def validation_errors(self, revision):
        errors = []
        duration = float(revision.get("duration") or 0)
        active = [word for word in revision.get("words", []) if not word.get("deleted")]
        previous = None
        for word in active:
            start, end = float(word["start"]), float(word["end"])
            if start < 0 or end <= start:
                errors.append(f"invalid timing for {word['id']}")
            if duration and end > duration:
                errors.append(f"word {word['id']} exceeds video duration")
            if previous is not None and start < float(previous["end"]):
                errors.append(f"word {word['id']} overlaps previous word")
            previous = word
        if not active:
            errors.append("transcript has no active words")
        return errors

    def approve(self, item_id, revision):
        document = self._load(item_id)
        if document["revisions"][-1]["revision"] != int(revision):
            raise RevisionConflict("only the latest revision can be approved")
        target = document["revisions"][-1]
        errors = self.validation_errors(target)
        if errors:
            raise ValidationError(errors)
        target["status"] = "approved"
        self._save(item_id, document)
        return copy.deepcopy(target)

    def render_segments(self, item_id, revision):
        data = self.get_revision(item_id, revision)
        errors = self.validation_errors(data)
        if errors:
            raise ValidationError(errors)
        grouped = {}
        for word in data["words"]:
            if word.get("deleted"):
                continue
            grouped.setdefault(word["segment_index"], []).append({
                "word": word["word"],
                "start": word["start"],
                "end": word["end"],
                "probability": word.get("probability"),
            })
        segments = []
        for index in sorted(grouped):
            words = grouped[index]
            segments.append({
                "start": words[0]["start"],
                "end": words[-1]["end"],
                "text": "".join(word["word"] for word in words),
                "words": words,
            })
        return segments
