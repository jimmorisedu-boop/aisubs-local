import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.output_planner import plan_output_paths


class OutputPlannerTests(unittest.TestCase):
    def test_existing_and_duplicate_names_receive_unique_suffixes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "output"
            output.mkdir()
            (output / "clip_captioned.mp4").write_bytes(b"existing")
            videos = [root / "a" / "clip.mp4", root / "b" / "clip.mp4"]

            planned = plan_output_paths(videos, output)

            self.assertEqual(
                [output / "clip_captioned_2.mp4", output / "clip_captioned_3.mp4"],
                [Path(path) for path in planned],
            )


if __name__ == "__main__":
    unittest.main()
