import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("webview", types.SimpleNamespace(FileDialog=object))

import app


class CreatorChannelTests(unittest.TestCase):
    def setUp(self):
        self.api = app.Api.__new__(app.Api)

    @mock.patch("webbrowser.open", return_value=True)
    def test_opens_only_the_fixed_creator_channel(self, open_browser):
        action = getattr(self.api, "open_creator_channel", lambda: None)

        result = action()

        self.assertEqual({"ok": True}, result)
        open_browser.assert_called_once_with(
            "https://t.me/daipotestit", new=2
        )

    @mock.patch("webbrowser.open", return_value=False)
    def test_reports_when_windows_refuses_to_open_a_browser(self, open_browser):
        result = self.api.open_creator_channel()

        self.assertFalse(result["ok"])
        self.assertIn("браузер", result["error"].lower())

    @mock.patch("webbrowser.open", side_effect=OSError("browser unavailable"))
    def test_reports_browser_launch_exceptions(self, open_browser):
        result = self.api.open_creator_channel()

        self.assertEqual(
            {"ok": False, "error": "browser unavailable"}, result
        )


if __name__ == "__main__":
    unittest.main()
