import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pipeline


TRANSCRIPT = {
    "language": "ru",
    "duration": 1.0,
    "device": "cpu",
    "segments": [{
        "start": 0.0,
        "end": 0.5,
        "text": " тест",
        "words": [{"word": " тест", "start": 0.0, "end": 0.5, "probability": 1.0}],
    }],
}


class PipelinePhaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.video = Path(self.temp.name) / "clip.mp4"
        self.video.write_bytes(b"first")
        self.cache = Path(self.temp.name) / "cache"

    def tearDown(self):
        self.temp.cleanup()

    def test_cache_identity_includes_model_language_and_source_version(self):
        first = pipeline.transcript_cache_path(self.video, "small", "ru", self.cache)
        other_model = pipeline.transcript_cache_path(self.video, "medium", "ru", self.cache)
        other_language = pipeline.transcript_cache_path(self.video, "small", "en", self.cache)
        self.video.write_bytes(b"changed source")
        changed_source = pipeline.transcript_cache_path(self.video, "small", "ru", self.cache)

        self.assertEqual(4, len({first, other_model, other_language, changed_source}))

    def test_transcription_phase_returns_data_without_rendering(self):
        with patch.object(pipeline.transcribe_mod, "transcribe", return_value=TRANSCRIPT), \
                patch.object(pipeline.renderer_mod, "render_captions") as renderer:
            artifact = pipeline.transcribe_phase(
                self.video, model_size="small", language="ru",
                cache_dir=self.cache, use_cached_transcript=False,
            )

        self.assertEqual(TRANSCRIPT["segments"], artifact["transcript"]["segments"])
        self.assertTrue(Path(artifact["words_json"]).exists())
        renderer.assert_not_called()

    def test_render_phase_uses_supplied_revision_segments(self):
        output = Path(self.temp.name) / "out.mp4"
        segments = TRANSCRIPT["segments"]
        with patch.object(pipeline.renderer_mod, "render_captions", return_value=str(output)) as renderer:
            result = pipeline.render_phase(self.video, output, segments, style={"font_size": 50})

        self.assertEqual(str(output), result["output"])
        renderer.assert_called_once_with(
            str(self.video), segments, str(output), style={"font_size": 50}, progress_cb=None
        )

    def test_render_phase_rejects_empty_transcript_before_encoding_video(self):
        output = Path(self.temp.name) / "empty.mp4"
        with patch.object(pipeline.renderer_mod, "render_captions") as renderer:
            with self.assertRaisesRegex(ValueError, "no speech"):
                pipeline.render_phase(self.video, output, [])

        renderer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
