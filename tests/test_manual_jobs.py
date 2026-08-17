import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.manual_jobs import ManualJobService


def transcript_for(text):
    return {
        "language": "ru",
        "duration": 2.0,
        "segments": [{
            "start": 0.1,
            "end": 0.8,
            "text": " " + text,
            "words": [{
                "word": " " + text, "start": 0.1, "end": 0.8, "probability": 0.95,
            }],
        }],
    }


class ManualJobServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.good = root / "good.mp4"
        self.bad = root / "bad.mp4"
        self.good.write_bytes(b"good")
        self.bad.write_bytes(b"bad")
        self.rendered = []

        def transcribe(path, **_params):
            if Path(path).name == "bad.mp4":
                raise RuntimeError("audio cannot be decoded")
            return {"transcript": transcript_for("готово"), "cached": False}

        def render(path, output, segments, **_params):
            self.rendered.append((Path(path).name, Path(output).name, segments))
            return {"output": str(output)}

        self.service = ManualJobService(root / "revisions", transcribe, render)

    def tearDown(self):
        self.temp.cleanup()

    def test_failed_file_does_not_stop_batch_transcription(self):
        job = self.service.create_job([self.bad, self.good], {"model_size": "small"})
        self.service.run_transcription(job["job_id"])
        snapshot = self.service.snapshot(job["job_id"])

        self.assertEqual(["failed", "transcribed"], [item["state"] for item in snapshot["items"]])
        self.assertEqual("audio cannot be decoded", snapshot["items"][0]["error"])

    def test_render_gate_opens_for_approved_items_after_all_transcriptions_are_terminal(self):
        job = self.service.create_job([self.good, self.bad], {"model_size": "small"})
        first_id = job["items"][0]["item_id"]
        self.service.run_transcription(job["job_id"])
        revision = self.service.get_transcript(first_id)
        self.service.approve(first_id, revision["revision"])

        snapshot = self.service.snapshot(job["job_id"])
        self.assertTrue(snapshot["render_ready"])
        self.assertEqual(1, snapshot["approved_count"])

    def test_batch_render_only_processes_approved_items(self):
        job = self.service.create_job([self.good, self.bad], {"model_size": "small"})
        self.service.run_transcription(job["job_id"])
        first = job["items"][0]
        revision = self.service.get_transcript(first["item_id"])
        self.service.approve(first["item_id"], revision["revision"])

        result = self.service.run_render(job["job_id"], {}, Path(self.temp.name) / "output")

        self.assertEqual(1, result["completed"])
        self.assertEqual(1, result["skipped"])
        self.assertEqual(["good.mp4"], [entry[0] for entry in self.rendered])

    def test_retry_can_process_only_selected_failed_items(self):
        attempts = {"bad.mp4": 0}

        def succeeds_on_retry(path, **_params):
            name = Path(path).name
            attempts[name] = attempts.get(name, 0) + 1
            if name == "bad.mp4" and attempts[name] == 1:
                raise RuntimeError("temporary decoder error")
            return {"transcript": transcript_for("повтор"), "cached": False}

        self.service.transcribe_fn = succeeds_on_retry
        job = self.service.create_job([self.bad, self.good], {"model_size": "small"})
        self.service.run_transcription(job["job_id"])
        bad_id = job["items"][0]["item_id"]
        self.service.run_transcription(job["job_id"], selected_ids=[bad_id])

        snapshot = self.service.snapshot(job["job_id"])
        self.assertEqual(["transcribed", "transcribed"], [item["state"] for item in snapshot["items"]])
        self.assertEqual(2, attempts["bad.mp4"])
        self.assertEqual(1, attempts["good.mp4"])

    def test_cancelled_item_can_be_retried(self):
        job = self.service.create_job([self.good], {"model_size": "small"})
        item_id = job["items"][0]["item_id"]
        self.service.run_transcription(job["job_id"], cancelled=lambda: True)
        self.assertEqual("cancelled", self.service.snapshot(job["job_id"])["items"][0]["state"])

        self.service.run_transcription(job["job_id"], selected_ids=[item_id])

        self.assertEqual("transcribed", self.service.snapshot(job["job_id"])["items"][0]["state"])

    def test_retranscription_keeps_previous_approved_revision(self):
        job = self.service.create_job([self.good], {"model_size": "small"})
        item_id = job["items"][0]["item_id"]
        self.service.run_transcription(job["job_id"])
        first = self.service.get_transcript(item_id)
        self.service.approve(item_id, first["revision"])

        self.service.retranscribe(item_id)

        latest = self.service.get_transcript(item_id)
        self.assertEqual(2, latest["revision"])
        self.assertEqual("transcribed", self.service.snapshot(job["job_id"])["items"][0]["state"])
        self.assertEqual("approved", self.service.store.get_revision(item_id, 1)["status"])

    def test_job_and_transcript_are_recovered_after_service_restart(self):
        job = self.service.create_job([self.good], {"model_size": "small"})
        item_id = job["items"][0]["item_id"]
        self.service.run_transcription(job["job_id"])

        restarted = ManualJobService(
            Path(self.temp.name) / "revisions", self.service.transcribe_fn, self.service.render_fn
        )

        recovered = restarted.snapshot(job["job_id"])
        self.assertEqual("transcribed", recovered["items"][0]["state"])
        self.assertEqual(" готово", restarted.get_transcript(item_id)["words"][0]["word"])
        self.assertEqual(job["job_id"], restarted.latest_snapshot()["job_id"])


if __name__ == "__main__":
    unittest.main()
