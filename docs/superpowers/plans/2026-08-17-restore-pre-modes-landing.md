# Restore Pre-Modes Landing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the exact AISubs GitHub Pages landing that existed before Auto/Manual received separate presentation, while retaining a small `@daipotestit` footer link.

**Architecture:** Use commit `1637010` / blob `faacabe6550501b5058eb3b93af3971862ea5699` as the canonical page source. Change only the public-page contract test and the autonomous `docs/index.html`; keep product code, README, screenshots, and the newer unreferenced CSS files untouched.

**Tech Stack:** Static HTML5 with embedded CSS, Python 3 `unittest`, Node.js built-in test runner, GitHub Pages from `main:/docs`, Git/GitHub CLI.

## Global Constraints

- Restore the sections and ordering from commit `1637010`.
- Do not add a modes section, Auto/Manual comparison, or a new redesign.
- Add only one content change to the historical page: a small footer link to `https://t.me/daipotestit`.
- Keep all repository links pointed at `https://github.com/jimmorisedu-boop/aisubs-local`.
- Do not modify product logic, Auto/Manual behavior, batch behavior, README, installer, or screenshots.
- Keep `docs/tokens.css` and `docs/landing.css` in the repository but do not reference them from the restored page.
- Verify widths 320, 375, 414, 768, and 1280 pixels without horizontal overflow.
- Publish directly from branch `main` after all checks pass.

---

## File Structure

- Modify `tests/test_public_presence.py`: define the public contract for the restored historical page, its six screenshots, and the retained Telegram link.
- Modify `docs/index.html`: restore the self-contained historical landing and add the small footer link.
- Do not modify `docs/tokens.css` or `docs/landing.css`: they remain dormant recovery artifacts for the technical landing saved in commit `2a84e59`.

### Task 1: Replace the technical-page contract with the historical-page contract

**Files:**
- Modify: `tests/test_public_presence.py`
- Test: `tests/test_public_presence.py`

**Interfaces:**
- Consumes: `PageContractParser`, `ROOT`, and the local files under `docs/`.
- Produces: assertions that require the six historical section headings, six historical screenshots, GitHub and Telegram destinations, and absence of a standalone modes block.

- [ ] **Step 1: Replace the technical structure test with the historical structure test**

Use exact heading copy so the test protects the remembered information architecture rather than implementation-only IDs:

```python
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
```

- [ ] **Step 2: Update the destination and image assertions**

Require the retained channel and every image referenced by the historical page:

```python
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
```

- [ ] **Step 3: Replace the current technical-copy assertions**

Protect the historical product explanation and explicitly reject the later mode-specific presentation:

```python
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
```

- [ ] **Step 4: Run the changed contract and confirm it fails on the current technical page**

Run:

```powershell
python -m unittest tests.test_public_presence.GitHubPagesTests -v
```

Expected: failures for missing historical headings/images and presence of the current modes section.

- [ ] **Step 5: Commit the failing contract**

```powershell
git add -- tests/test_public_presence.py
git commit -m "test: define pre-modes landing contract"
```

### Task 2: Restore the historical standalone page and retain the channel link

**Files:**
- Modify: `docs/index.html`
- Test: `tests/test_public_presence.py`

**Interfaces:**
- Consumes: historical source `git show 1637010:docs/index.html`, existing images under `docs/`, and the contract from Task 1.
- Produces: a self-contained static page whose content matches blob `faacabe6` except for the footer channel link.

- [ ] **Step 1: Read and verify the canonical source before editing**

```powershell
git rev-parse 1637010:docs/index.html
git show 1637010:docs/index.html | Select-String -Pattern '<h2>|<img|<footer'
```

Expected blob: `faacabe6550501b5058eb3b93af3971862ea5699`; expected headings and images are exactly those listed in Task 1.

- [ ] **Step 2: Restore `docs/index.html` with `apply_patch`**

Replace the current file with the complete output of `git show 1637010:docs/index.html`. Do not translate, shorten, reformat, or copy any Auto/Manual block from later commits. The restored document must remain one autonomous HTML file with its historical embedded `<style>` block.

- [ ] **Step 3: Add the single approved footer difference with `apply_patch`**

The final footer body must be:

```html
<footer>
  <div class="wrap">
    Код под лицензией MIT ·
    <a href="https://github.com/jimmorisedu-boop/aisubs-local">github.com/jimmorisedu-boop/aisubs-local</a>
    · <a href="https://t.me/daipotestit">@daipotestit</a>
  </div>
</footer>
```

- [ ] **Step 4: Prove that the only semantic difference from the historical file is the channel link**

```powershell
git diff 1637010 -- docs/index.html
```

Expected: the footer channel link is the only changed line relative to the historical page.

- [ ] **Step 5: Run the focused public-page tests**

```powershell
python -m unittest tests.test_public_presence -v
```

Expected: all screenshot, GitHub Pages, and README presence tests pass.

- [ ] **Step 6: Check formatting and local asset resolution**

```powershell
git diff --check
python -m unittest tests.test_public_presence.GitHubPagesTests.test_local_assets_resolve_without_external_runtime_dependencies -v
```

Expected: no whitespace errors and the asset test passes.

- [ ] **Step 7: Commit the restored page**

```powershell
git add -- docs/index.html
git commit -m "docs: restore pre-modes landing"
```

### Task 3: Verify the complete repository and publish GitHub Pages

**Files:**
- Verify: `docs/index.html`
- Verify: `tests/test_public_presence.py`
- Verify: repository-wide Python and Node test suites

**Interfaces:**
- Consumes: committed outputs from Tasks 1 and 2.
- Produces: verified `main`, pushed to `origin/main`, with a successful GitHub Pages deployment.

- [ ] **Step 1: Run the complete automated test suites**

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
node --test tests/*.test.js
```

Expected: every Python and Node test passes; no application behavior test is changed to accommodate the landing.

- [ ] **Step 2: Serve the page locally**

```powershell
python -m http.server 8000 --directory docs
```

Expected: `http://localhost:8000/` returns the restored page and all six images load without 404 responses.

- [ ] **Step 3: Perform responsive browser verification**

At viewport widths 320, 375, 414, 768, and 1280 pixels, verify:

- no horizontal document overflow;
- all six section headings are readable in the historical order;
- screenshots fit their containers;
- GitHub and `@daipotestit` links receive keyboard focus and open the correct destinations;
- no Auto/Manual comparison block appears.

- [ ] **Step 4: Verify branch scope before publishing**

```powershell
git status -sb
git log --oneline origin/main..main
git diff --stat origin/main..main
```

Expected: branch is `main`; commits contain only the specification, plan, test contract, and restored landing; the worktree is clean.

- [ ] **Step 5: Push `main`**

```powershell
git push origin main
```

Expected: `origin/main` advances to the verified restoration commit.

- [ ] **Step 6: Verify GitHub Pages deployment**

```powershell
$pagesRun = gh run list --workflow pages-build-deployment --branch main --limit 1 --json databaseId --jq '.[0].databaseId'
gh run watch $pagesRun --exit-status
```

Expected: the newest Pages workflow for `main` completes successfully and `https://jimmorisedu-boop.github.io/aisubs-local/` serves the restored headings plus the `@daipotestit` footer link.
