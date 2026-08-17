import struct
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PageContractParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.links = []
        self.images = []
        self.external_runtime_assets = []
        self.heading_counts = {"h1": 0, "h2": 0}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        if tag == "a" and values.get("href"):
            self.links.append(values["href"])
        if tag == "img":
            self.images.append((values.get("src"), values.get("alt", "")))
        if tag in self.heading_counts:
            self.heading_counts[tag] += 1
        asset = values.get("src") if tag == "script" else values.get("href")
        if tag in {"script", "link"} and asset and asset.startswith(("http://", "https://")):
            self.external_runtime_assets.append(asset)


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


class GitHubPagesTests(unittest.TestCase):
    def setUp(self):
        self.path = ROOT / "docs" / "index.html"
        self.parser = PageContractParser()
        self.parser.feed(self.path.read_text(encoding="utf-8"))

    def test_landing_page_has_the_approved_six_sections(self):
        required = {"hero", "modes", "workflow", "trust", "quick-start", "site-footer"}

        self.assertTrue(required.issubset(self.parser.ids))
        self.assertEqual(1, self.parser.heading_counts["h1"])
        self.assertGreaterEqual(self.parser.heading_counts["h2"], 4)

    def test_public_destinations_and_product_proof_are_present(self):
        self.assertIn("https://github.com/jimmorisedu-boop/aisubs-local", self.parser.links)
        self.assertIn("https://t.me/daipotestit", self.parser.links)
        images = {src: alt for src, alt in self.parser.images}
        self.assertIn("screenshot-manual.png", images)
        self.assertIn("screenshot.png", images)
        self.assertTrue(images["screenshot-manual.png"].strip())
        self.assertTrue(images["screenshot.png"].strip())

    def test_local_assets_resolve_without_external_runtime_dependencies(self):
        self.assertEqual([], self.parser.external_runtime_assets)
        for src, _ in self.parser.images:
            if src and not src.startswith(("http://", "https://", "/")):
                self.assertTrue((self.path.parent / src).is_file(), src)


if __name__ == "__main__":
    unittest.main()
