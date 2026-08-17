import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(os.name == "nt", "setup.bat is Windows-only")
class SetupEncodingTests(unittest.TestCase):
    def test_russian_header_is_emitted_as_utf8(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "setup.bat").read_text(encoding="utf-8")
        prefix = source.split('set "PYTHONNOUSERSITE=1"', 1)[0]

        with tempfile.TemporaryDirectory() as temp:
            harness = Path(temp) / "setup-header.bat"
            launcher = Path(temp) / "launcher.bat"
            harness.write_text(prefix + "\nchcp\nexit /b 0\n", encoding="utf-8")
            launcher.write_text(
                f'@echo off\nchcp 866 >nul\ncall "{harness}"\n', encoding="ascii"
            )
            result = subprocess.run(
                ["cmd.exe", "/d", "/c", str(launcher)],
                cwd=root,
                capture_output=True,
                check=True,
            )

        output = result.stdout.decode("utf-8", errors="replace")
        self.assertIn("AISubs - первичная установка", output)
        self.assertIn("Будет скачано", output)
        self.assertRegex(output, r"(?m)65001\s*$")


if __name__ == "__main__":
    unittest.main()
