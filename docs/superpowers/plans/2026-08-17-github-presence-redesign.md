# AISubs GitHub Presence Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Present AISubs consistently in the desktop app, README, GitHub Pages, and repository metadata as an offline Windows batch-subtitling tool with equal Auto and Manual workflows.

**Architecture:** Keep the product runtime unchanged except for one narrow fixed-URL bridge method and one secondary header control. Treat README as the detailed documentation source and GitHub Pages as a six-section product landing page, both backed by current real-interface screenshots and stdlib-only contract tests.

**Tech Stack:** Python 3 `unittest`, pywebview, vanilla HTML/CSS/JavaScript, Node.js built-in test runner, GitHub Pages, GitHub CLI.

## Global Constraints

- Public product copy is Russian-only.
- Primary call to action is exactly `Открыть на GitHub`.
- Primary audience is video editors and small studios; emphasize batch throughput, control, and saved time.
- Auto and Manual are equal workflows; no change may make Auto/batch slower or harder to discover or operate.
- GitHub Pages remains one responsive standalone HTML file with no external JavaScript, framework, analytics, cookies, or build step.
- The desktop control opens only `https://t.me/daipotestit`; do not expose an arbitrary URL opener through pywebview.
- Screenshots must come from the current real interface and contain only synthetic demo filenames and transcript text.
- Do not claim exact processing speed without measured benchmark data.
- No English version, packaged Windows release, installer redesign, or broader desktop-app redesign.

---

## File Map

- `app.py` — expose the fixed creator-channel action to pywebview and return a structured result.
- `gui/index.html` — render the compact, keyboard-accessible channel control in the app header.
- `gui/app.js` — invoke the backend action and surface a non-blocking failure toast.
- `tests/test_creator_channel.py` — prove fixed-URL success, browser refusal, and exception behavior.
- `tests/test_public_presence.py` — validate public copy contracts, local links, screenshot presence, and PNG dimensions.
- `docs/screenshot-manual.png` — current Manual workflow hero image.
- `docs/screenshot.png` — refreshed current Auto/batch workflow image.
- `docs/index.html` — short six-section product landing page.
- `README.md` — detailed installation, Auto, Manual, recovery, CLI, architecture, and license documentation.

### Task 1: Safe creator-channel backend action

**Files:**
- Modify: `app.py:8-22,211-215`
- Create: `tests/test_creator_channel.py`

**Interfaces:**
- Consumes: Python standard-library `webbrowser.open(url, new=2)`.
- Produces: `CREATOR_CHANNEL_URL: str` and `Api.open_creator_channel() -> dict[str, object]`, returning `{"ok": True}` or `{"ok": False, "error": str}`.

- [ ] **Step 1: Write failing backend contract tests**

```python
import unittest
from unittest import mock

import app


class CreatorChannelTests(unittest.TestCase):
    def setUp(self):
        self.api = app.Api.__new__(app.Api)

    @mock.patch("app.webbrowser.open", return_value=True)
    def test_opens_only_the_fixed_creator_channel(self, open_browser):
        result = self.api.open_creator_channel()

        self.assertEqual({"ok": True}, result)
        open_browser.assert_called_once_with(
            "https://t.me/daipotestit", new=2
        )

    @mock.patch("app.webbrowser.open", return_value=False)
    def test_reports_when_windows_refuses_to_open_a_browser(self, open_browser):
        result = self.api.open_creator_channel()

        self.assertFalse(result["ok"])
        self.assertIn("браузер", result["error"].lower())

    @mock.patch("app.webbrowser.open", side_effect=OSError("browser unavailable"))
    def test_reports_browser_launch_exceptions(self, open_browser):
        result = self.api.open_creator_channel()

        self.assertEqual(
            {"ok": False, "error": "browser unavailable"}, result
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the focused tests and verify the missing API fails**

Run: `python -m unittest tests.test_creator_channel -v`

Expected: FAIL because `app.webbrowser` and `Api.open_creator_channel` do not exist.

- [ ] **Step 3: Implement the smallest fixed-URL bridge**

Add `import webbrowser` with the standard-library imports, define the URL near the existing path constants, and add this method beside `open_output_folder`:

```python
CREATOR_CHANNEL_URL = "https://t.me/daipotestit"


def open_creator_channel(self):
    try:
        if not webbrowser.open(CREATOR_CHANNEL_URL, new=2):
            return {"ok": False, "error": "Не удалось открыть браузер"}
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
```

- [ ] **Step 4: Run the focused tests and the existing Python regression suite**

Run: `python -m unittest tests.test_creator_channel -v`

Expected: 3 tests PASS.

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Expected: all tests PASS; no Auto pipeline, output planning, Manual job, revision, or setup encoding regression.

- [ ] **Step 5: Commit the backend action**

```bash
git add app.py tests/test_creator_channel.py
git commit -m "feat: add safe creator channel action"
```

### Task 2: Secondary creator link in the desktop header

**Files:**
- Modify: `gui/index.html:54-80,376-387`
- Modify: `gui/app.js:752-772`
- Create: `tests/test_public_presence.py`

**Interfaces:**
- Consumes: `Api.open_creator_channel() -> {ok: bool, error?: str}` from Task 1 and existing `showToast(message)`.
- Produces: DOM control `#creatorChannel` and async global function `openCreatorChannel()`.

- [ ] **Step 1: Write a failing static UI contract test**

```python
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DesktopPresenceTests(unittest.TestCase):
    def test_header_exposes_secondary_creator_channel_action(self):
        html = (ROOT / "gui" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "gui" / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="creatorChannel"', html)
        self.assertIn('type="button"', html)
        self.assertIn('@daipotestit', html)
        self.assertIn('aria-label="Открыть канал проекта в Telegram"', html)
        self.assertIn('async function openCreatorChannel()', script)
        self.assertIn('api().open_creator_channel()', script)
        self.assertIn('showToast(', script)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the static UI test and verify it fails**

Run: `python -m unittest tests.test_public_presence.DesktopPresenceTests -v`

Expected: FAIL because `#creatorChannel` is absent.

- [ ] **Step 3: Add the non-drag header button without moving the mode switch**

Place the control after the product subtitle and before `.spacer`, keeping the mode switch and GPU badge at the right edge:

```html
<button
  class="creator-link"
  id="creatorChannel"
  type="button"
  aria-label="Открыть канал проекта в Telegram"
  onclick="openCreatorChannel()"
>@daipotestit ↗</button>
```

Add secondary styling and an explicit focus state:

```css
.creator-link{
  border:0; background:transparent; color:var(--text-dim);
  padding:6px 8px; border-radius:7px; cursor:pointer; font-size:12px;
  -webkit-app-region:no-drag;
}
.creator-link:hover{ color:var(--text); background:var(--panel-2); }
.creator-link:focus-visible{ outline:2px solid var(--accent); outline-offset:2px; }
```

Do not alter `.mode-switch`, the Auto default, or any queue/run control.

- [ ] **Step 4: Add failure handling through the existing toast system**

```javascript
async function openCreatorChannel() {
  try {
    const result = await api().open_creator_channel();
    if (!result || !result.ok) {
      showToast("Не удалось открыть @daipotestit: " +
        ((result && result.error) || "неизвестная ошибка"));
    }
  } catch (error) {
    showToast("Не удалось открыть @daipotestit: " + String(error));
  }
}
```

- [ ] **Step 5: Run syntax, static contract, and browser-failure smoke checks**

Run: `node --check gui/app.js`

Expected: exit 0.

Run: `python -m unittest tests.test_public_presence.DesktopPresenceTests -v`

Expected: PASS.

Temporarily stub `window.pywebview.api.open_creator_channel` to return `{"ok": false, "error": "test"}` in the locally served UI, activate `#creatorChannel`, and verify a toast appears while Auto remains selected and the batch run button remains available.

- [ ] **Step 6: Commit the desktop control**

```bash
git add gui/index.html gui/app.js tests/test_public_presence.py
git commit -m "feat: link creator channel from app"
```

### Task 3: Current Auto and Manual product screenshots

**Files:**
- Modify: `tests/test_public_presence.py`
- Create: `docs/screenshot-manual.png`
- Modify: `docs/screenshot.png`

**Interfaces:**
- Consumes: current `gui/index.html`, `gui/app.js`, `gui/manual-review.js`, and synthetic local demo state.
- Produces: two same-size PNG assets at 1440×900 pixels with no private data.

- [ ] **Step 1: Add a failing stdlib PNG asset contract**

```python
import struct


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
        self.assertGreater(auto.stat().st_size, 100_000)
        self.assertGreater(manual.stat().st_size, 100_000)
        self.assertEqual((1440, 900), png_dimensions(auto))
        self.assertEqual(png_dimensions(auto), png_dimensions(manual))
```

- [ ] **Step 2: Run the screenshot contract and verify the missing Manual asset fails**

Run: `python -m unittest tests.test_public_presence.ScreenshotTests -v`

Expected: FAIL because `docs/screenshot-manual.png` is absent or the existing Auto image has old dimensions.

- [ ] **Step 3: Capture the Manual hero from the real interface**

Add `.superpowers/` to `.git/info/exclude` (local repository metadata, never committed), then use a 1440×900 viewport and a temporary fixture under `.superpowers/screenshots/` to seed only data, not controls. Show at least four synthetic files in different useful states, a selected transcript containing synthetic Russian words and word timings, an attention marker, an approval count, and the batch render action. Confirm the visible controls all exist in the production HTML before capturing `docs/screenshot-manual.png`.

- [ ] **Step 4: Capture the Auto/batch screenshot from the same interface and viewport**

Switch through the real `#modeAuto` control. Show a multi-file queue, one real style preview, style controls, the unchanged batch run action, and the compact channel link. Capture `docs/screenshot.png` at exactly 1440×900.

- [ ] **Step 5: Inspect both images and run the asset contract**

Inspect both PNG files at full size. Reject any personal path, unreadable transcript, clipped CTA, browser chrome, temporary debug control, or unimplemented state.

Run: `python -m unittest tests.test_public_presence.ScreenshotTests -v`

Expected: PASS with equal 1440×900 dimensions.

- [ ] **Step 6: Commit the refreshed assets and contract**

```bash
git add docs/screenshot.png docs/screenshot-manual.png tests/test_public_presence.py
git commit -m "docs: refresh Auto and Manual screenshots"
```

### Task 4: Six-section GitHub Pages landing page

**Files:**
- Modify: `docs/index.html`
- Modify: `tests/test_public_presence.py`

**Interfaces:**
- Consumes: `docs/screenshot-manual.png`, `docs/screenshot.png`, repository URL, and fixed Telegram URL.
- Produces: standalone responsive Russian landing page with section IDs `hero`, `modes`, `workflow`, `trust`, `quick-start`, and `site-footer`.

- [ ] **Step 1: Add failing Pages information-architecture and local-link tests**

```python
import re


class GitHubPagesTests(unittest.TestCase):
    def setUp(self):
        self.path = ROOT / "docs" / "index.html"
        self.html = self.path.read_text(encoding="utf-8")

    def test_landing_page_has_the_approved_six_sections(self):
        for section_id in (
            "hero", "modes", "workflow", "trust", "quick-start", "site-footer"
        ):
            self.assertIn(f'id="{section_id}"', self.html)
        self.assertIn("Проверьте слова. Запустите весь пакет.", self.html)
        self.assertIn(">Открыть на GitHub<", self.html)
        self.assertIn("Авто", self.html)
        self.assertIn("Мануал", self.html)

    def test_public_links_and_assets_resolve(self):
        self.assertIn("https://t.me/daipotestit", self.html)
        self.assertIn("https://github.com/jimmorisedu-boop/aisubs-local", self.html)
        for relative in re.findall(r'(?:src|href)="([^"#:?]+)"', self.html):
            if relative.startswith(("http://", "https://", "/")):
                continue
            self.assertTrue((self.path.parent / relative).is_file(), relative)

    def test_page_has_no_external_runtime_dependency(self):
        self.assertNotRegex(self.html, r'<script[^>]+src="https?://')
        self.assertNotRegex(self.html, r'<link[^>]+href="https?://')
```

- [ ] **Step 2: Run the Pages tests and verify the old structure fails**

Run: `python -m unittest tests.test_public_presence.GitHubPagesTests -v`

Expected: FAIL because the approved section IDs and Manual workflow are absent.

- [ ] **Step 3: Replace the old walkthrough with the approved product-first structure**

Build semantic `header`, `main`, `section`, and `footer` elements in this exact order:

```html
<header id="hero">...</header>
<main>
  <section id="modes">...</section>
  <section id="workflow">...</section>
  <section id="trust">...</section>
  <section id="quick-start">...</section>
</main>
<footer id="site-footer">...</footer>
```

The hero must contain `OFFLINE · WINDOWS · BATCH`, the approved headline, concise batch/control copy, `Открыть на GitHub`, and `screenshot-manual.png` with descriptive Russian alt text. The modes section gives Auto and Manual equal card weight and includes the Auto screenshot. Workflow lists add batch → review ready transcripts → bulk approve → render approved items. Trust covers offline files, retained word timings, collision-safe output names, and restart recovery. Quick start shows `setup.bat → run.bat`. Footer includes GitHub, README, MIT, Windows, and `Проект и обновления: @daipotestit`.

- [ ] **Step 4: Implement responsive and accessibility behavior**

Use the existing dark product palette, visible `:focus-visible` outlines, semantic links, logical `h1` → `h2` hierarchy, two-column desktop mode/workflow layouts, and a single-column breakpoint at 760px. Ensure CTA text and screenshots remain within the viewport at 320px width and that no CSS suppresses focus outlines.

- [ ] **Step 5: Run contracts and inspect desktop/mobile/zoom states**

Run: `python -m unittest tests.test_public_presence.GitHubPagesTests -v`

Expected: all Pages tests PASS.

Serve: `python -m http.server 8765 --directory docs`

Inspect `http://localhost:8765/` at 1440×900, 390×844, and 200% zoom. Verify heading order, both modes, CTA focus, local images, no horizontal overflow, and readable footer links.

- [ ] **Step 6: Commit GitHub Pages**

```bash
git add docs/index.html tests/test_public_presence.py
git commit -m "docs: redesign GitHub Pages for batch workflows"
```

### Task 5: README as the detailed source of truth

**Files:**
- Modify: `README.md`
- Modify: `tests/test_public_presence.py`

**Interfaces:**
- Consumes: current commands and architecture from the existing README plus the Manual behavior implemented in `gui/manual-review.js` and `lib/manual_jobs.py`.
- Produces: detailed Russian documentation linked to Pages and `@daipotestit`.

- [ ] **Step 1: Add a failing README coverage test**

```python
class ReadmeTests(unittest.TestCase):
    def test_readme_documents_current_product_and_recovery_states(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        required = (
            "https://jimmorisedu-boop.github.io/aisubs-local/",
            "https://t.me/daipotestit",
            "docs/screenshot-manual.png",
            "## Авто или Мануал",
            "## Авто: пакет без остановок",
            "## Мануал: проверка перед рендером",
            "автосохран",
            "тайминг",
            "Повторить ошибки",
            "восстанов",
            "## Командная строка",
            "## Устройство проекта",
            "## Лицензии",
        )
        for text in required:
            self.assertIn(text, readme)

    def test_readme_relative_images_resolve(self):
        path = ROOT / "README.md"
        readme = path.read_text(encoding="utf-8")
        for target in re.findall(r'!\[[^]]*\]\(([^)]+)\)', readme):
            if target.startswith(("http://", "https://", "/")):
                continue
            self.assertTrue((path.parent / target).is_file(), target)
```

- [ ] **Step 2: Run the README contract and verify current documentation fails**

Run: `python -m unittest tests.test_public_presence.ReadmeTests -v`

Expected: FAIL because Manual mode, recovery, and the creator channel are undocumented.

- [ ] **Step 3: Rewrite the opening and workflow documentation**

Use this order: concise product/privacy overview; Pages and Telegram links; Manual screenshot; Auto/Manual comparison table; features; requirements; installation; Auto workflow; Manual workflow; cache and safe output behavior; typography/styling; CLI; architecture; licenses and final project/update link.

In the comparison, describe Auto as the fastest hands-off batch path and Manual as transcript/timing review before one approved batch render. Document observed controls and states only: autosave, word text/timing edits, approve/unapprove, attention warnings, retry failed transcriptions, cancellation boundaries, re-transcription, recovery after restart, partial success, and collision-safe output names.

- [ ] **Step 4: Preserve accurate technical commands and licenses**

Keep the working `setup.bat`, `run.bat`, model download, CUDA explanation, `transcribe.py`, render/CLI examples, font licenses, Whisper/faster-whisper attribution, and project tree. Update file descriptions for `gui/manual-review.js`, `gui/manual-state.js`, `lib/manual_jobs.py`, `lib/transcript_revisions.py`, and the new screenshots. Do not add benchmark numbers or claim that first-time model downloads work offline.

- [ ] **Step 5: Run README and link validation**

Run: `python -m unittest tests.test_public_presence.ReadmeTests tests.test_public_presence.GitHubPagesTests -v`

Expected: all tests PASS and every relative README image/link resolves.

- [ ] **Step 6: Commit README**

```bash
git add README.md tests/test_public_presence.py
git commit -m "docs: document Auto and Manual production workflows"
```

### Task 6: Full regression, publication, and GitHub metadata

**Files:**
- Verify: `app.py`, `gui/index.html`, `gui/app.js`, `gui/manual-review.js`, `gui/manual-state.js`, `README.md`, `docs/index.html`, `docs/screenshot.png`, `docs/screenshot-manual.png`
- Remote update: `jimmorisedu-boop/aisubs-local` About description, homepage, and topics.

**Interfaces:**
- Consumes: all deliverables from Tasks 1–5 and authenticated `git`/`gh` access.
- Produces: pushed redesign on `main`, deployed GitHub Pages, and verified repository metadata.

- [ ] **Step 1: Run every automated test and syntax check from a clean process**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Expected: all Python tests PASS.

Run: `node --test tests/manual-state.test.js`

Expected: all Manual state tests PASS.

Run: `node --check gui/app.js && node --check gui/manual-review.js && node --check gui/manual-state.js`

Expected: all commands exit 0.

- [ ] **Step 2: Smoke-test both complete desktop workflows**

Launch `run.bat`. In Auto, add at least two disposable videos, confirm Auto is selected by default, start the batch, observe per-file progress, cancel only at the documented file boundary, and confirm completed outputs remain available. In Manual, transcribe a disposable batch, edit one word and timing, approve items, render the approved batch, and restart the app to confirm recovery. Activate `@daipotestit ↗` once with the normal browser and once with a stubbed failure result; confirm success leaves the app responsive and failure produces only a toast.

- [ ] **Step 3: Verify the working tree contains only intentional changes**

Run: `git status --short`

Expected: no tracked modifications and only intentionally ignored local screenshot fixtures; `.superpowers/` must not be staged.

Run: `git diff main...HEAD --check`

Expected: exit 0.

- [ ] **Step 4: Push the feature branch and merge it to main**

```bash
git push -u origin codex/github-presence-redesign
gh pr create --base main --head codex/github-presence-redesign --title "Redesign AISubs GitHub presence" --body "Обновляет приложение, README и GitHub Pages для Auto/Manual batch-сценариев; добавляет безопасную ссылку @daipotestit."
gh pr merge --merge --delete-branch
git switch main
git pull --ff-only origin main
```

Expected: PR merged, local `main` equals `origin/main`, and all project files remain at repository root rather than inside an extra nesting directory.

- [ ] **Step 5: Update GitHub About metadata after main contains the files**

Run:

```bash
gh repo edit jimmorisedu-boop/aisubs-local --description "Офлайн-приложение Windows для пакетных субтитров: Auto/Manual, редактор слов и таймингов, Whisper и пословная подсветка." --homepage "https://jimmorisedu-boop.github.io/aisubs-local/"
gh repo edit jimmorisedu-boop/aisubs-local --add-topic batch-processing --add-topic faster-whisper --add-topic video-editing
```

Expected: existing relevant topics remain and the three topics are added.

- [ ] **Step 6: Verify the remote repository and deployment**

Run: `gh repo view jimmorisedu-boop/aisubs-local --json description,homepageUrl,repositoryTopics,defaultBranchRef,url`

Expected: the approved Russian description, Pages homepage, expected topics, and `main` default branch are returned.

Open `https://jimmorisedu-boop.github.io/aisubs-local/` after Pages finishes deploying. Verify the new headline, Manual hero, both mode descriptions, Telegram footer link, and GitHub CTA. Re-run the public URLs from a private browser window to catch cache or permission issues.

- [ ] **Step 7: Record final publication evidence**

Report the merged PR URL, final `main` commit, passing Python/Node test counts, GitHub Pages URL, About description, topics, and any smoke-test limitations. Do not claim the deployment succeeded until the live URL shows the new page.
