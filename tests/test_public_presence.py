import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def png_dimensions(path):
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"Not a PNG: {path}")
    return struct.unpack(">II", data[16:24])


class ScreenshotTests(unittest.TestCase):
    def test_product_screenshots_are_current_and_consistent(self):
        auto = ROOT / "docs" / "screenshot.png"
        manual = ROOT / "docs" / "screenshot-manual.png"

        self.assertTrue(auto.is_file())
        self.assertTrue(manual.is_file())
        self.assertGreater(auto.stat().st_size, 50_000)
        self.assertGreater(manual.stat().st_size, 50_000)
        self.assertEqual((1440, 900), png_dimensions(auto))
        self.assertEqual(png_dimensions(auto), png_dimensions(manual))


if __name__ == "__main__":
    unittest.main()
