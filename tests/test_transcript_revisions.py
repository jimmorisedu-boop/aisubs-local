import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.transcript_revisions import RevisionConflict, TranscriptStore, ValidationError


SAMPLE = {
    "language": "ru",
    "duration": 3.0,
    "segments": [{
        "start": 0.2,
        "end": 1.4,
        "text": " Привет мир",
        "words": [
            {"word": " Привет", "start": 0.2, "end": 0.8, "probability": 0.98},
            {"word": " мир", "start": 0.9, "end": 1.4, "probability": 0.72},
        ],
    }],
}


class TranscriptStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = TranscriptStore(Path(self.temp.name))
        self.original = self.store.create(
            "item-1", "C:/video.mp4", SAMPLE, {"model": "small", "language": "ru"}
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_replacing_word_preserves_timing_and_marks_draft(self):
        word = self.original["words"][0]
        draft = self.store.apply_patch(
            "item-1", self.original["revision"],
            [{"op": "replace", "word_id": word["id"], "text": " Здравствуйте"}],
        )

        self.assertEqual(" Здравствуйте", draft["words"][0]["word"])
        self.assertEqual((0.2, 0.8), (draft["words"][0]["start"], draft["words"][0]["end"]))
        self.assertEqual("needs_review", draft["status"])

    def test_approval_rejects_overlapping_word_timing(self):
        second = self.original["words"][1]
        draft = self.store.apply_patch(
            "item-1", self.original["revision"],
            [{"op": "set_timing", "word_id": second["id"], "start": 0.7, "end": 1.4}],
        )

        with self.assertRaises(ValidationError):
            self.store.approve("item-1", draft["revision"])

    def test_edit_after_approval_does_not_mutate_approved_snapshot(self):
        approved = self.store.approve("item-1", self.original["revision"])
        word = approved["words"][0]
        self.store.apply_patch(
            "item-1", approved["revision"],
            [{"op": "replace", "word_id": word["id"], "text": " Изменено"}],
        )

        saved_approved = self.store.get_revision("item-1", approved["revision"])
        self.assertEqual(" Привет", saved_approved["words"][0]["word"])
        self.assertEqual("approved", saved_approved["status"])

    def test_stale_patch_is_rejected(self):
        word = self.original["words"][0]
        self.store.apply_patch(
            "item-1", self.original["revision"],
            [{"op": "replace", "word_id": word["id"], "text": " Первый"}],
        )

        with self.assertRaises(RevisionConflict):
            self.store.apply_patch(
                "item-1", self.original["revision"],
                [{"op": "replace", "word_id": word["id"], "text": " Второй"}],
            )

    def test_retranscription_appends_revision_without_destroying_approved_snapshot(self):
        approved = self.store.approve("item-1", self.original["revision"])
        replacement = dict(SAMPLE)
        replacement["segments"] = [{
            "start": 0.3, "end": 0.9, "text": " Новый",
            "words": [{"word": " Новый", "start": 0.3, "end": 0.9, "probability": 0.99}],
        }]

        new_original = self.store.create(
            "item-1", "C:/video.mp4", replacement, {"model": "medium", "language": "ru"}
        )

        self.assertEqual(2, new_original["revision"])
        self.assertEqual("original", new_original["status"])
        self.assertEqual("approved", self.store.get_revision("item-1", approved["revision"])["status"])
        self.assertEqual(" Привет", self.store.get_revision("item-1", approved["revision"])["words"][0]["word"])


if __name__ == "__main__":
    unittest.main()
