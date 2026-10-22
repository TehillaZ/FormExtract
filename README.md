# FormExtract — commitment-form extraction engine

Extracts the required fields from Hebrew lab commitment forms (printed, scanned, photographed or handwritten) with a vision model, **flags every value it is not sure about**, and stores approved records in a database behind a REST API. A lab technician reviews the flagged values in a Hebrew right-to-left web app, corrects or confirms them, and approves.

Guiding principle: an empty, flagged field is always better than a guessed value. The system is judged not only by how often it is right, but by how well it knows when it is wrong.

> Design, decisions (ADRs), results and the schedule live in [PLAN.md](PLAN.md) (English; the UI itself is Hebrew).

## Where the project stands

The full path works end to end: upload, processing, review, correction, approval. What is still open is mostly **measuring accuracy at scale** (blocked by the free-tier model quota) and a few screens.

| Area | State |
|---|---|
| Ingest (PDF, images, HEIC), perspective fix, deskew, contrast, barcodes (decoded plain, binarized and enlarged: 55 of the 97 numbers on the samples) | done |
| Orientation: sideways scans turned locally, upside-down scans flipped after a model check | done; 4 browser tests, but accuracy effect measured on only 2 real pages |
| Extraction with a vision model (Gemini), normalization, per-field confidence with reasons | done |
| Closed sender list (55 senders) with fuzzy matching, ID check digit (`strict` / `lenient`); an ID counts as verified only when it is also corroborated (read twice, or highlighted: PLAN ADR-019) | done |
| Gemini model fallback list and quota-aware retries | done (see Known limitations) |
| Groq as a second provider | done and measured: `qwen/qwen3.8-27b`, lower accuracy than Gemini 2.5 Flash, about 50 pages a day (see PLAN 10.2) |
| Database (PostgreSQL, SQLAlchemy): save, search, correct, confirm, approve, duplicate warnings | done |
| REST API (FastAPI) with background processing | done |
| Web app: upload, table, form review (collapsible form list, zoom, magnifier, expanded view, inline editing, one-click confirm) | done |
| Records screen: search by name, ID or number; filter by status, sender and received date; paging with a real total | done |
| Export of the filtered records to Excel or CSV | done |
| Accuracy-report screen: saved evaluation runs side by side, with what was not measured | done; shows one report so far |
| Tests: 221 backend, 202 frontend, 40 browser end-to-end | done |
| Evaluation against hand-verified ground truth, dev/test split | done; **test set run on 11 of 14 pages (3 left for the next quota)** |
| Template hints, a second model call for uncertain fields | not started |
| Attach / split forms in the UI | not started (not needed by the samples) |
| Marking field positions on the image | not started (needs coordinates from the model) |
| One-command start (`start.ps1` / `start.sh`) and a demo from saved answers (`seed_demo.py`) | done |
| Keyboard shortcuts in the review screen (↑↓ forms, N next to review, A approve a clean form, L list) | done |
| Timing a 30-page batch | not done (blocked by the daily quota) |

## How it works

```
file → page images → turn sideways pages → local enhancement → local barcodes
     → one vision-model call per page (structured JSON)
       (if the model says the page is upside down: flip it and ask once more)
     → normalization + validation + confidence → DB (status: pending)
     → human review (orange = needs a look) → confirm or correct → approve
```

Confidence is **not** taken from the model. It is computed by our code (`backend/app/pipeline/extract.py`):

- **high**: independently verified, e.g. barcode match, ID passing the check digit (strict mode), exact sender-list match.
- **medium**: consistent reading with no verification.
- **low**: failed a check, handwritten and unverified, inconsistent reads, or not found. A missing field stays empty and is flagged "not found".

Anything not `high` is shown in orange. A person clears a flag by **correcting** the value (logged: old value, new value, time) or by **confirming** it as it stands (not logged as a correction). Saving an empty value confirms that the form really has none (PLAN ADR-017).

Commitment numbers: each record has its own UUID key, so a missing number is fine. Approved records may not share a commitment number (partial unique index); duplicates among pending records are only a warning (PLAN ADR-010, ADR-016).

## Setup

Developed on Python 3.14 and Node 25; any recent versions should work (not tested on others).

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # Windows; use .venv/bin/pip on Linux/macOS
cp ../.env.example ../.env                          # then fill in GEMINI_API_KEY (and GROQ_API_KEY if you can reach it)
```

Database (PostgreSQL 16): `docker compose up -d db` from the repo root. There are no schema migrations yet: after a schema change, reset the dev database.

### Run the app: one command

```powershell
.\start.ps1 -Seed        # Windows: database, interface, API on one server; -Seed fills it with the sample forms
./start.sh --seed        # Linux / macOS / Git Bash
```

Then open **http://localhost:8000**. The first run builds the interface (`npm install` and `npm run build`); add `-Rebuild` after changing the frontend. The API serves the built interface (`app.web:root`), so the demo needs no Node process and only one terminal. Docker Desktop must be running.

### Run the app: development (two terminals, with hot reload)

```bash
# terminal 1: API on :8000 (needs the database above and a vision key in .env)
cd backend && .venv/Scripts/python -m uvicorn app.api.main:app --port 8000

# terminal 2: UI on :5173 (proxies /api to the API)
cd frontend && npm install && npm run dev
```

Open http://localhost:5173, upload forms in the "העלאה" tab, then review them in "טבלה" or "טופס". Restart the API after changing backend code (it does not reload).

### Tests

| Layer | Command | What it covers |
|---|---|---|
| Backend | `cd backend && python -m pytest` | pipeline rules, validation, database, API, records filters and totals, export, saved reports, quota handling, orientation (170 tests, SQLite) |
| Backend on PostgreSQL | `TEST_DATABASE_URL=postgresql+psycopg://hakaton:hakaton@localhost:5432/hakaton_test python -m pytest tests/test_repo.py` | the same database tests against the real engine. The database name must end in `_test`: these tests drop every table |
| Frontend unit and component | `cd frontend && npm test` | logic and behaviour in a simulated browser (166 tests) |
| Frontend type check and lint | `npx tsc -b` and `npx oxlint` | |
| Browser end-to-end | `cd frontend && npm run test:e2e` | the real frontend and real API in real Chromium: layout, zoom, the collapsible list, saving, confirming, approving, sideways / upside-down scans, the records screen, downloads, and the accuracy screen (38 tests) |

The browser tests start their own servers (API on :8100, UI on :5174) with an in-memory database and a scripted vision model (`backend/e2e/server.py`, which also holds two saved accuracy reports and can seed many records at once). They never touch your data and never use API quota. First time only: `npx playwright install chromium`. Use `npm run test:e2e:ui` to watch them run. The six test pages are generated by `python -m e2e.make_fixtures` (run from `backend/`): a page's width selects the scripted answer, and a black marker block in one corner lets the scripted model tell whether a page is the right way up.

### Evaluating the model

This is the project's "eval": the same pages and ground truth, scored the same way, every time the model or prompt changes.

```bash
cd backend
python scripts/evaluate.py --provider gemini --split dev                  # calls the API, caches the answers
python scripts/evaluate.py --provider gemini --split dev --cached-only    # re-score from the cache, no API calls
python scripts/evaluate.py --provider gemini --pages p1_03 --no-orient    # measure what orientation correction adds
python scripts/diff_cache.py <cache-folder-name>                          # per-page disagreements with ground truth

# two models on exactly the pages both scored (no API calls; fill the caches with evaluate.py first)
python scripts/compare.py --a gemini:gemini-2.5-flash --a-no-orient --b groq:qwen/qwen3.8-27b --split dev --skip-sideways --detail
```

A pinned `--model` never falls back to another model, so one report is one model. The accuracy screen shows reports side by side but **refuses to show a difference between reports that cover different pages**; `compare.py` is the fair comparison.

A run over a whole split (or everything) also saves a small report to `data/eval_reports/`, which the **דוח דיוק** tab shows: up to three reports side by side, the change in accuracy between them, the number of pages behind every column, and a warning while the test set has not been run. A hand-picked `--pages` list is never saved, and `--no-save` skips saving.

For each field it reports accuracy, % flagged, and **errors that were not flagged** (the metric that matters most, because those reach the database unnoticed). Answers are cached in `data/eval_cache/<provider>-<model>-<prompt-hash>[-oriented]/`, so changing the prompt starts a fresh cache and re-scoring costs nothing. `data/split.json` reserves 14 pages as a **test set**: do not tune prompts on them. Results so far are in PLAN section 10.

## A demo that does not need a model

Free-tier quotas can run out and networks can block a provider, so the sample forms can be loaded **without calling any model**:

```bash
python scripts/seed_demo.py --dry-run     # what would be loaded, and from which saved answer
python scripts/seed_demo.py               # load them (also: .\start.ps1 -Seed)
```

It takes the model answers already saved in `data/eval_cache` and replays them through the **real pipeline** (turning the page, enhancement, barcodes, normalization, confidence, storage), replacing only the model call. Today that gives **44 forms**: 18 from Gemini 2.5 Flash, 2 from Gemini 3.5 Flash and 13 from Groq Qwen. Every record's provider reads for example `gemini:gemini-2.5-flash (saved answer)`, so it is never mistaken for a live run: **say so when you present it.** Running it again changes nothing. Needs `data/pages` (see below). Five sideways sample scans are still upside down after the turn; `data/sample_orientation.json` lists them so the replay shows them upright (PLAN ADR-020).

## Roles and passwords

The interface opens on a password screen. Two passwords in `.env` (`USER_PASSWORD`, `DEVELOPER_PASSWORD`; see `.env.example`) decide the role: a **user** gets העלאה, טבלה, טופס and רשומות; a **developer** also gets דוח דיוק and טעויות חוזרות. The server enforces it too: every route except `/health` needs the session cookie, and `/evaluation` and `/corrections/summary` need the developer role. A role whose password is empty cannot log in, there is no default password. Limits: no lockout after wrong guesses, and passwords are sent in the clear, so use HTTPS if the server is ever not on localhost.

## Exporting records

The **רשומות** tab has two export buttons that download every record matching the filters on screen (not only the current page):

- **Excel** (`.xlsx`) is for people: a right-to-left sheet, real dates, and IDs stored as text so leading zeros survive.
- **CSV** is for programs: UTF-8 with a byte-order mark so Excel shows Hebrew, and ISO dates. Excel drops the leading zeros of an ID when it opens a CSV, so use the Excel file for that.

Text read from a form is untrusted, so a cell that starts with `=`, `+`, `-` or `@` can never run as a formula: in CSV it is prefixed with an apostrophe, and in Excel it is stored as text. **An export contains names and ID numbers: treat the file like patient data.**

## Data not in the repo

`data/pages/` (rendered page images), `data/storage/` (uploaded images) and the sample PDFs are git-ignored. Put the two sample PDFs in the repo root and, from `backend/`, run `python -m scripts.render_samples ../<part1>.pdf ../<part2>.pdf --out ../data/pages` to regenerate the images (it also writes `barcodes.json`). `data/ground_truth_draft.jsonl` (hand-verified from the yellow highlights), `data/split.json` and the evaluation cache are tracked.

## Assumptions

Learned from the samples rather than the task text (PLAN ADR-013):

- One record per form, holding lists of central numbers and commitment numbers.
- Central numbers are 6 digits, recognised by the word "מרכזי" near the sticker. A 6-digit number alone is not enough.
- If an institution sent the patient (hospital, lab, IDF…), it is the sender; otherwise the HMO.
- If a stamp date and a handwritten date differ, the stamp wins and the field is flagged with both values.
- Sample IDs are fake and many fail the check digit (13 of 48 have 8 or 10 digits). Flagging them is correct.
- Yellow highlights are not relied on (real forms may not have them). The model extracts by content and context: labels such as "התחייבות", "דרישה", "דגימה", "מרכזי" and the position on the form. When a highlight exists it only raises confidence and breaks ties; it is never a condition (PLAN ADR-021).

## Smart memory

When people keep fixing the same reading the same way on one sender's forms (at least 3 times, 75% agreeing), the next form with that reading shows a suggestion: "on earlier forms from this sender, X was corrected to Y (3 of 3)". It is only applied when the user presses the button (PLAN ADR-023). The "טעויות חוזרות" tab lists all repeated corrections.

To show a suggestion before any real corrections exist, run `python scripts/seed_suggestion_demo.py` from `backend/` (it writes into the database named in `.env`). It saves three earlier forms from one sender, corrects the same wrong central number on each through the real correction code, and reads a new form with that same wrong number, so the suggestion is computed by the real rule. These records are named "דמו" and their provider says "demo": say it is demo data. `--dry-run` shows what it would do; running it twice changes nothing.

## Deploying to Render

`Dockerfile` builds the interface and the API into one image, and `render.yaml` describes one web service plus one Postgres database.

1. Push the repository to GitHub. In Render: **New > Blueprint**, pick the repository.
2. It asks for `GEMINI_API_KEY` (and `GROQ_API_KEY`). The two passwords are generated: read them in the service's **Environment** tab.
3. The first deploy takes a few minutes. Open the service URL and log in.

Things to know before relying on it:
- **Uploaded images do not last** on the free plan: its disk is erased on every deploy and restart. Records stay in the database, but a form's image disappears. A persistent disk (paid) or cloud image storage is needed to keep them.
- A page that is being read when the service restarts stays "בעיבוד" (not recovered yet).
- The free plan sleeps when idle and its database expires after a while: check Render's current terms.
- The cookie is not yet marked Secure, and wrong passwords are not rate-limited.
- The image was not built end to end on the development machine (its network blocked pip's certificate check), so the first Render build is the real test.

## Known limitations

- **Model quota.** The Gemini free tier allows **20 requests per day per model**. The provider walks a list of models (`GEMINI_FALLBACK_MODELS`), which gives roughly 80 a day, but accuracy across those models has not been compared, and some newer models answer slowly. A 40-form stack is possible only with fallbacks, and a real lab needs a paid tier or a local model. Pre-processed demo results remain the safety net.
- **Accuracy is not established.** The measured numbers cover 21 development pages (plus 2 sideways pages), on yellow-highlighted samples, so they are probably optimistic. The held-out test set was run on 11 of 14 pages (1 error in 55 values was not flagged); see SUMMARY.md. Handwritten digits are often misread; they are flagged, not guessed.
- **Handwritten names are never trusted**: always flagged.
- Upside-down pages (180°) are detected only through the model's own flag, at the cost of one extra call per such page.
- Two forms on one page, and forms spanning several pages, are not supported (none exist in the samples).
- **Groq** reads images with one model only (`qwen/qwen3.8-27b`) and is limited to 200,000 tokens a day (about 50 pages) and 8,000 a minute. It was less accurate than Gemini 2.5 Flash on 16 shared pages.
- **`gemini-3.5-flash` is slow** (about 100 seconds a page), so a batch on it would take close to an hour.
- No login, no schema migrations, one local server (PLAN ADR-005, ADR-011).
- Exported files contain names and IDs and are not protected in any way once downloaded.

## Privacy

- Orientation, barcodes and image enhancement run locally.
- Only the page image is sent to the external model. Field values are not written to logs.
- On the free Gemini tier, inputs may be used by Google to improve products. That is acceptable for the altered sample data, **not** for real patient data. In a real lab, use a paid tier or a local model.
- Page images are meant to be deleted 30 days after approval (configurable; not implemented yet).
