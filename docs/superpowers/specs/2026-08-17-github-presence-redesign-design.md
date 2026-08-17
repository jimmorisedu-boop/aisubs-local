# AISubs GitHub Presence Redesign

## Objective

Update the repository presentation so GitHub About, README, GitHub Pages, and
the desktop application describe the current AISubs product consistently.
The redesign must communicate the new Auto and Manual workflows to video
editors and small studios, with emphasis on batch throughput, transcript
control, and time saved.

The public content remains Russian-only. The primary call to action is
`Открыть на GitHub`.

## Audience and Positioning

Primary audience:

- freelance video editors;
- small editing and content studios;
- operators processing multiple short-form videos at once.

Core promise:

> Проверьте слова. Запустите весь пакет.

AISubs is positioned as a local Windows production tool, not a cloud service
or a generic Whisper frontend. The page should prove three things quickly:

1. it handles a batch rather than one file at a time;
2. users can choose between a fully automatic path and transcript review;
3. video and audio stay on the user's computer.

## Visual Direction

The approved direction is **Dual Product / Product First**:

- dark interface-derived palette already used by AISubs;
- restrained blue-to-violet accent gradient;
- large product screenshot rather than an abstract illustration;
- compact technical labels and proof points suitable for professional users;
- minimal decorative motion and no external frontend dependencies.

The hero uses a real Manual Mode screenshot because transcript review and
batch approval are the product's clearest differentiators. Auto Mode receives
its own full-width section below rather than a small inset that makes it look
secondary.

## GitHub Pages Information Architecture

`docs/index.html` remains a single, responsive, standalone HTML document. It
has six sections:

1. **Product-first hero**
   - label: `OFFLINE · WINDOWS · BATCH`;
   - headline: `Проверьте слова. Запустите весь пакет.`;
   - short outcome-oriented copy;
   - primary CTA: `Открыть на GitHub`;
   - large current Manual Mode screenshot.
2. **Two modes**
   - Auto Mode: the queue runs through transcription and rendering without
     review stops;
   - Manual Mode: review ready transcripts, approve clean items in bulk, and
     render approved items as one batch;
   - neither mode is presented as an inferior or advanced variant.
3. **Studio workflow**
   - add the batch;
   - review transcripts as they become ready;
   - approve clean files in bulk;
   - render approved files together.
4. **Technical trust strip**
   - local/offline processing;
   - word-level timing survives text edits;
   - output names do not overwrite existing files;
   - drafts and batch state recover after restart.
5. **Quick start**
   - `setup.bat → run.bat`;
   - secondary CTA to the repository installation instructions.
6. **Footer**
   - GitHub, README, MIT license, Windows support;
   - `Проект и обновления: @daipotestit` linked to
     `https://t.me/daipotestit`.

The current long interface walkthrough, typography explanation, and detailed
pipeline diagram move out of Pages. Their useful technical content remains in
README, avoiding two independently maintained documentation sources.

## Screenshots

Two current screenshots are required:

- `docs/screenshot-manual.png`: hero image showing Manual Mode with a
  synthetic multi-file queue, transcript words and timings, attention state,
  approval count, and batch render action;
- `docs/screenshot.png`: refreshed Auto Mode image showing queue, live style
  preview, and style controls.

Screenshots must come from the real current HTML/CSS interface. Synthetic demo
filenames and transcript content are allowed, but no personal files or
unimplemented controls may appear. Temporary screenshot fixtures remain under
ignored local paths and are not committed.

Images should use the same viewport and crop, remain readable on a standard
GitHub page, and include descriptive Russian alt text.

## README Structure

README remains the detailed source of truth:

1. concise product overview and privacy statement;
2. links to GitHub Pages and `@daipotestit`;
3. current Manual Mode screenshot;
4. Auto versus Manual comparison;
5. feature summary;
6. requirements and installation;
7. Auto workflow;
8. Manual workflow, including autosave, word/timing editing, approval,
   warnings, retry, cancellation, re-transcription, and recovery;
9. caching and safe output behavior;
10. typography and styling;
11. CLI usage;
12. project architecture;
13. licenses and creator/update links.

Existing accurate CUDA, model size, CLI, typography, and license information
is preserved and reorganized rather than rewritten without need.

## GitHub Repository Metadata

GitHub About is updated after the files land on `main`.

Description:

> Офлайн-приложение Windows для пакетных субтитров: Auto/Manual, редактор слов и таймингов, Whisper и пословная подсветка.

Homepage remains:

`https://jimmorisedu-boop.github.io/aisubs-local/`

Keep existing relevant topics and add:

- `batch-processing`;
- `faster-whisper`;
- `video-editing`.

## Creator Channel in the Desktop Application

The application header gains a small keyboard-accessible control labeled
`@daipotestit ↗`, visually secondary to the mode switch.

The JavaScript control calls a narrow backend method
`open_creator_channel()`. The backend opens only the fixed URL
`https://t.me/daipotestit` in the system browser. It does not expose an
arbitrary URL opener to the webview.

The method returns a structured success/error result. If Windows cannot open
the browser, the UI shows a non-blocking toast and keeps AISubs usable.

## Accessibility and Responsive Behavior

- links and actions use semantic `a` or `button` elements;
- focus states remain visible;
- headings follow a logical hierarchy;
- screenshots have meaningful alt text;
- color is not the only distinction between Auto and Manual;
- the Pages layout collapses to one column below the existing mobile
  breakpoint;
- text and CTA remain usable at 200% zoom.

## Verification

Before publication:

- run the complete Python and Node test suites;
- add a Python test for `open_creator_channel()` success and failure results;
- validate that all local README and Pages links resolve;
- verify both screenshot files exist and have non-zero, matching dimensions;
- run JavaScript syntax checks;
- perform a desktop smoke-test of the channel control;
- serve `docs/` locally and inspect desktop and mobile widths in a browser;
- confirm GitHub Pages loads after merge;
- verify GitHub About description, homepage, and topics from the remote API.

## Non-goals

- no English version;
- no packaged Windows release or new installer format;
- no analytics, cookies, forms, or external frontend frameworks;
- no claims about exact processing speed without measured benchmark data;
- no redesign of the AISubs application beyond the creator channel link.
