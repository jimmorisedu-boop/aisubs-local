# AISubs Technical Landing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the promotional GitHub Pages layout with a concise, factual technical overview that preserves Auto as the fastest batch path and documents Manual as optional review control.

**Architecture:** Keep GitHub Pages as dependency-free static HTML served from `/docs`. Split design tokens and layout rules into `docs/tokens.css` and `docs/landing.css`; keep content and semantics in `docs/index.html`. Enforce the public contract with Python HTML-parser tests, then verify responsive behavior in the browser.

**Tech Stack:** HTML5, CSS custom properties, Python `unittest`, GitHub Pages.

## Global Constraints

- Modify only the GitHub Pages files, its public-presence test, Hallmark memory, and this plan/spec documentation.
- Preserve the existing dark palette and blue-violet accent.
- Do not add JavaScript, external runtime assets, analytics, forms, downloads, or a second language.
- Auto appears first and remains the shortest hands-off batch workflow.
- Manual is optional review before rendering, not a required step.
- Use only characteristics confirmed by the repository; do not publish benchmarks or unsupported format claims.
- Verify widths 320, 375, 414, 768, and 1280 pixels with no horizontal overflow.
- Do not modify README, application code, installer code, or existing product screenshots.

---

## File Structure

- `docs/index.html`: semantic content, link destinations, one Auto product screenshot.
- `docs/tokens.css`: all colors, font stacks, spacing, type sizes, rules, radii, and focus tokens.
- `docs/landing.css`: page layout, link states, responsive table transformation, reduced-motion rule.
- `tests/test_public_presence.py`: structural and factual contract for the deployed page and its local assets.
- `.hallmark/log.json`: newest-first record of the technical redesign.

### Task 1: Replace the marketing-page contract with a technical-page contract

**Files:**
- Modify: `tests/test_public_presence.py`

**Interfaces:**
- Consumes: `docs/index.html` parsed by `PageContractParser`.
- Produces: assertions for section IDs, factual copy, one screenshot, local stylesheets, and forbidden promotional copy.

- [ ] **Step 1: Extend the parser and write the failing technical-page tests**

Add stylesheet collection to `PageContractParser`:

```python
self.stylesheets = []

if tag == "link" and values.get("rel") == "stylesheet" and values.get("href"):
    self.stylesheets.append(values["href"])
```

Replace the six-section test with:

```python
def test_landing_page_has_the_technical_structure(self):
    required = {"overview", "modes", "specs", "install", "site-footer"}
    self.assertTrue(required.issubset(self.parser.ids))
    self.assertEqual(1, self.parser.heading_counts["h1"])
    self.assertEqual(3, self.parser.heading_counts["h2"])
```

Replace the product-proof test with one that requires `screenshot.png`, rejects `screenshot-manual.png`, and checks GitHub, installation, license, and Telegram targets:

```python
def test_public_destinations_and_single_product_capture_are_present(self):
    expected = {
        "https://github.com/jimmorisedu-boop/aisubs-local",
        "https://github.com/jimmorisedu-boop/aisubs-local#установка",
        "https://github.com/jimmorisedu-boop/aisubs-local/blob/main/LICENSE",
        "https://t.me/daipotestit",
    }
    self.assertTrue(expected.issubset(set(self.parser.links)))
    images = {src: alt for src, alt in self.parser.images}
    self.assertEqual({"screenshot.png"}, set(images))
    self.assertTrue(images["screenshot.png"].strip())
```

Add factual-copy and anti-marketing assertions:

```python
def test_copy_is_factual_and_not_promotional(self):
    html = self.path.read_text(encoding="utf-8")
    for fact in ("Windows 10/11", "faster-whisper", "ffmpeg", "setup.bat", "run.bat", "CPU", "CUDA"):
        self.assertIn(fact, html)
    for phrase in ("Проверьте слова. Запустите весь пакет.", "Меньше ожидания между монтажом", "Рабочий процесс студии"):
        self.assertNotIn(phrase, html)
```

Extend the local-assets test so every relative stylesheet also resolves:

```python
for href in self.parser.stylesheets:
    if not href.startswith(("http://", "https://", "/")):
        self.assertTrue((self.path.parent / href).is_file(), href)
```

- [ ] **Step 2: Run the focused tests and verify the new contract fails**

Run: `python -m unittest tests.test_public_presence.GitHubPagesTests -v`

Expected: FAIL because the current page has the old section IDs, two images, promotional phrases, and no `tokens.css`/`landing.css` links.

- [ ] **Step 3: Commit the failing contract**

```powershell
git add -- tests/test_public_presence.py
git commit -m "test: define concise technical landing contract"
```

### Task 2: Build the concise technical page

**Files:**
- Modify: `docs/index.html`
- Create: `docs/tokens.css`
- Create: `docs/landing.css`

**Interfaces:**
- Consumes: `docs/screenshot.png`; repository URLs fixed in Task 1.
- Produces: five semantic IDs, two local stylesheets, one responsive comparison table, and no runtime JavaScript.

- [ ] **Step 1: Create the complete token file**

Create `docs/tokens.css` with named OKLCH tokens for:

```css
:root {
  --color-paper: oklch(18% 0.02 273);
  --color-panel: oklch(22% 0.025 273);
  --color-ink: oklch(94% 0.01 273);
  --color-muted: oklch(72% 0.02 273);
  --color-rule: oklch(34% 0.03 273);
  --color-accent: oklch(72% 0.16 272);
  --color-accent-strong: oklch(80% 0.13 272);
  --color-focus: oklch(84% 0.15 100);
  --font-display: "Segoe UI", system-ui, sans-serif;
  --font-body: "Segoe UI", system-ui, sans-serif;
  --font-mono: "Cascadia Mono", "Consolas", monospace;
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-6: 1.5rem;
  --space-8: 2rem;
  --space-12: 3rem;
  --space-16: 4rem;
  --text-sm: 0.875rem;
  --text-body: 1rem;
  --text-lede: clamp(1.0625rem, 1.7vw, 1.25rem);
  --text-h2: clamp(1.25rem, 2.5vw, 1.75rem);
  --text-title: clamp(2rem, 5vw, 3.5rem);
  --rule-thin: 1px;
  --radius-sm: 0.375rem;
  --radius-md: 0.625rem;
  --dur-fast: 120ms;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
}
```

- [ ] **Step 2: Replace `docs/index.html` with the approved content hierarchy**

Use this semantic order:

```html
<header id="overview">
  <nav><!-- AISubs; GitHub; README --></nav>
  <h1>AISubs</h1>
  <p>Локальное Windows-приложение для пакетного создания субтитров с режимами Auto и Manual.</p>
  <ul aria-label="Краткие характеристики"><!-- Windows 10/11; локально; CPU/CUDA; faster-whisper + ffmpeg --></ul>
  <div><!-- GitHub; Установка; @daipotestit --></div>
  <figure><img src="screenshot.png" alt="Auto Mode AISubs: пакетная очередь видео и настройки субтитров"></figure>
</header>
<main>
  <section id="modes"><h2>Режимы обработки</h2><table><!-- Auto first; Manual second --></table></section>
  <section id="specs"><h2>Технические характеристики</h2><dl><!-- verified facts --></dl></section>
  <section id="install"><h2>Установка и запуск</h2><pre><code>setup.bat\nrun.bat</code></pre><!-- first model download caveat; README link --></section>
</main>
<footer id="site-footer"><!-- GitHub; README; MIT; @daipotestit --></footer>
```

Use exactly one factual paragraph per section. Do not restore the old headline, studio workflow, trust grid, quick-start card, or statement footer.

- [ ] **Step 3: Implement the responsive technical layout in `docs/landing.css`**

The stylesheet must:

- import `tokens.css` first;
- stamp `Technical Brief`, technical/austere tone, and cool anchor hue;
- set `overflow-x: clip` on both `html` and `body`;
- use a single centered content column with thin section rules;
- use no shadows, gradients, floating cards, decorative backgrounds, or motion on load;
- give every link default, visited, hover, focus-visible, and active states;
- keep clickable text on one line;
- make the screenshot responsive with `display: block; width: 100%; height: auto`;
- convert table rows to block sections below 640 px using `data-label` cells;
- include `@media (prefers-reduced-motion: reduce)` and remove transitions there.

- [ ] **Step 4: Run the focused contract and verify it passes**

Run: `python -m unittest tests.test_public_presence.GitHubPagesTests -v`

Expected: all GitHub Pages tests PASS.

- [ ] **Step 5: Run markup and stylesheet sanity checks**

Run:

```powershell
python -m unittest tests.test_public_presence -v
rg -n "<script|https?://.*\.(css|js)|Проверьте слова|Меньше ожидания|Рабочий процесс студии" docs/index.html
git diff --check
```

Expected: public-presence tests PASS; `rg` returns no matches; diff check is clean.

- [ ] **Step 6: Commit the technical page**

```powershell
git add -- docs/index.html docs/tokens.css docs/landing.css
git commit -m "docs: replace promotional landing with technical overview"
```

### Task 3: Record the redesign, verify it visually, and publish

**Files:**
- Modify: `.hallmark/log.json`

**Interfaces:**
- Consumes: the completed static page from Task 2.
- Produces: Hallmark project memory, browser evidence, passing regression suite, and a synchronized `origin/main`.

- [ ] **Step 1: Add the newest Hallmark memory entry**

Prepend this entry and retain the prior entry after it:

```json
{
  "date": "2026-08-17",
  "macrostructure": "Technical Brief",
  "theme": "AISubs dark",
  "theme_axes": "dark / system-sans / cool",
  "enrichment": "single real Auto product capture",
  "brief": "Concise technical GitHub Pages overview without promotional copy"
}
```

- [ ] **Step 2: Serve `/docs` locally and inspect the desktop layout**

Run a temporary local HTTP server from `docs`, open it in the in-app browser, and verify at 1280×800:

- AISubs title and the factual description appear before any screenshot;
- GitHub, installation, and channel links are visible;
- the Auto screenshot is the only screenshot;
- the page reads as a compact technical reference rather than a sales page;
- no clipped content or horizontal overflow exists.

- [ ] **Step 3: Verify all required responsive widths**

At 320, 375, 414, and 768 px, collect `document.documentElement.scrollWidth` and `clientWidth`. Expected: equal at every width. Confirm all clickable labels remain one line and the Auto/Manual table becomes vertical below 640 px.

- [ ] **Step 4: Run the Hallmark slop test and correct every failure**

Check the finished page against all 58 Hallmark gates. Expected: 58/58, including no giant slogan, no repeated CTA, no bento grid, no fake chrome, no external fonts, no horizontal scroll, and no two-line link labels.

- [ ] **Step 5: Run the full regression suite**

Run:

```powershell
python -m unittest discover -s tests -v
node --test tests/*.test.js
node --check gui/app.js
node --check gui/manual-review.js
node --check gui/manual-state.js
node --check gui/creator-channel.js
git diff --check
```

Expected: all Python and Node tests PASS, syntax checks exit 0, and diff check is clean.

- [ ] **Step 6: Commit Hallmark memory and any verified fixes**

```powershell
git add -- .hallmark/log.json tests/test_public_presence.py docs/index.html docs/tokens.css docs/landing.css
git commit -m "docs: verify concise technical landing"
```

If all tracked content is already committed, do not create an empty commit.

- [ ] **Step 7: Push directly to `main` and verify deployment**

```powershell
git push origin main
gh run list --workflow pages-build-deployment --limit 1
```

Wait for the run whose `headSha` equals local `HEAD`; require `status=completed` and `conclusion=success`. Confirm `git rev-parse HEAD` equals the SHA returned by `git ls-remote origin refs/heads/main`.

- [ ] **Step 8: Verify the live source contract**

Use GitHub's contents API for `docs/index.html?ref=main` and confirm the deployed source contains `AISubs`, `Технические характеристики`, `setup.bat`, and `@daipotestit`, and excludes `Проверьте слова. Запустите весь пакет.`. Open the public Pages URL when transport permits.
