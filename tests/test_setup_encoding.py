"""The installer must survive cmd.exe's code page.

Originally this checked that setup.bat itself printed Russian text after a
`chcp 65001`. That approach did not actually work: cmd.exe reads a .bat in the
OEM code page, and the multi-byte characters break the parsing of lines
continued with `^`, so the installer collapsed into "not recognized" errors
before it downloaded anything.

The installer now keeps setup.bat pure ASCII and puts the logic in setup.ps1,
so these tests check the property that matters - the installer runs and prints
readable Russian - rather than one particular implementation of it.
"""

import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SetupEncodingTests(unittest.TestCase):
    def test_launcher_is_pure_ascii(self):
        """Non-ASCII in a .bat is what corrupted parsing in the first place."""
        raw = (ROOT / "setup.bat").read_bytes()
        offenders = [b for b in raw if b > 127]
        self.assertEqual(
            offenders, [],
            "setup.bat must stay ASCII-only: cmd.exe reads it in the OEM code page",
        )

    def test_launcher_has_no_line_continuations(self):
        """Continued lines are where the byte-level corruption showed up."""
        lines = (ROOT / "setup.bat").read_text(encoding="ascii").splitlines()
        continued = [l for l in lines if l.rstrip().endswith("^")]
        self.assertEqual(continued, [], "setup.bat must not use '^' continuations")

    def test_powershell_script_has_utf8_bom(self):
        """Windows PowerShell 5.1 reads a BOM-less file as ANSI and mangles Russian."""
        raw = (ROOT / "setup.ps1").read_bytes()
        self.assertTrue(
            raw.startswith(b"\xef\xbb\xbf"),
            "setup.ps1 must start with a UTF-8 BOM or PowerShell 5.1 misreads it",
        )

    @unittest.skipUnless(os.name == "nt", "setup.bat is Windows-only")
    def test_installer_runs_and_prints_readable_russian(self):
        """End to end through cmd.exe, exactly how a user starts it."""
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", str(ROOT / "setup.bat"), "-Model", "skip", "-DryRun"],
            cwd=ROOT, capture_output=True, timeout=180,
        )
        output = result.stdout.decode("utf-8", errors="replace")

        broken = [l for l in output.splitlines() if "is not recognized" in l]
        self.assertEqual(broken, [], "installer produced cmd parsing errors")

        self.assertIn("AISubs", output)
        self.assertIn("Будет скачано", output)
        self.assertIn("модель распознавания", output)


if __name__ == "__main__":
    unittest.main()
