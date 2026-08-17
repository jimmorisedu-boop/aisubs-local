import struct
import unittest
import re
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PageContractParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.links = []
        self.images = []
        self.stylesheets = []
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
        if tag == "link" and values.get("rel") == "stylesheet" and values.get("href"):
            self.stylesheets.append(values["href"])
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

    def test_landing_page_restores_the_pre_modes_structure(self):
        html = self.path.read_text(encoding="utf-8")
        headings = (
            "Что умеет",
            "Интерфейс по частям",
            "Типографика без ручной правки",
            "Как всё устроено",
            "Установка",
            "Требования",
        )

        self.assertEqual(1, self.parser.heading_counts["h1"])
        self.assertEqual(6, self.parser.heading_counts["h2"])
        for heading in headings:
            self.assertIn(f"<h2>{heading}</h2>", html)
        self.assertNotIn('id="modes"', html)
        self.assertNotIn("Режимы обработки", html)

    def test_public_destinations_and_historical_product_captures_are_present(self):
        expected_links = {
            "https://github.com/jimmorisedu-boop/aisubs-local",
            "https://t.me/daipotestit",
        }
        expected_images = {
            "screenshot.png",
            "ui-input.png",
            "ui-preview.png",
            "ui-presets.png",
            "ui-style.png",
            "ui-style-2.png",
        }

        self.assertTrue(expected_links.issubset(set(self.parser.links)))
        images = {src: alt for src, alt in self.parser.images}
        self.assertEqual(expected_images, set(images))
        for alt in images.values():
            self.assertTrue(alt.strip())

    def test_copy_matches_the_pre_modes_product_explanation(self):
        html = self.path.read_text(encoding="utf-8")

        for phrase in (
            "Whisper",
            "ffmpeg",
            "setup.bat",
            "run.bat",
            "Windows 10 или 11",
            "Типографика без ручной правки",
        ):
            self.assertIn(phrase, html)
        for phrase in (
            "Режимы обработки",
            "Два режима. Одна очередь.",
            "AUTO",
            "MANUAL",
        ):
            self.assertNotIn(phrase, html)

    def test_local_assets_resolve_without_external_runtime_dependencies(self):
        self.assertEqual([], self.parser.external_runtime_assets)
        for src, _ in self.parser.images:
            if src and not src.startswith(("http://", "https://", "/")):
                self.assertTrue((self.path.parent / src).is_file(), src)
        for href in self.parser.stylesheets:
            if not href.startswith(("http://", "https://", "/")):
                self.assertTrue((self.path.parent / href).is_file(), href)


class ReadmeTests(unittest.TestCase):
    def setUp(self):
        self.path = ROOT / "README.md"
        self.markdown = self.path.read_text(encoding="utf-8")

    def test_readme_links_to_the_product_page_channel_and_manual_proof(self):
        targets = re.findall(r"\[[^]]*\]\(([^)]+)\)", self.markdown)

        self.assertIn("https://jimmorisedu-boop.github.io/aisubs-local/", targets)
        self.assertIn("https://t.me/daipotestit", targets)
        self.assertIn("docs/screenshot-manual.png", targets)

    def test_readme_relative_images_resolve(self):
        for target in re.findall(r"!\[[^]]*\]\(([^)]+)\)", self.markdown):
            if target.startswith(("http://", "https://", "/")):
                continue
            self.assertTrue((self.path.parent / target).is_file(), target)


if __name__ == "__main__":
    unittest.main()
