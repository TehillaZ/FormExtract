# FormExtract — commitment-form extraction engine

Extracts the required fields from Hebrew lab commitment forms (printed, scanned, photographed or handwritten) with a vision model, **flags every value it is not sure about**, and stores approved records in a database behind a REST API. A lab technician reviews the flagged values in a Hebrew right-to-left web app, corrects or confirms them, and approves.

Guiding principle: an empty, flagged field is always better than a guessed value. The system is judged not only by how often it is right, but by how well it knows when it is wrong.

> Design, decisions (ADRs), results and the schedule live in [PLAN.md](PLAN.md) (English; the UI itself is Hebrew).

## Where the project stands

The full path works end to end: upload, processing, review, correction, approval. What is still open is mostly **measuring accuracy at scale** (blocked by the free-tier model quota) and a few screens.

| Area | State |
|---|---|
| Ingest (PDF, images, HEIC), perspective fix, deskew, contrast, barcodes | done |
| Orientation: sideways scans turned locally, upside-down scans flipped after a model check | done; 4 browser tests, but accuracy effect measured on only 2 real pages |
| Extraction with a vision model (Gemini), normalization, per-field confidence with reasons | done |
| Closed sender list (55 senders) with fuzzy matching, ID check digit (`strict` / `lenient`) | done |
| Gemini model fallback list and quota-aware retries | done (see Known limitations) |
| Groq as a second provider | code done; blocked on the development network, never measured |
| Database (PostgreSQL, SQLAlchemy): save, search, correct, confirm, approve, duplicate warnings | done |
| REST API (FastAPI) with background processing | done |
| Web app: upload, table, form review (collapsible form list, zoom, magnifier, expanded view, inline editing, one-click confirm) | done, first version |
| Tests: 92 backend, 98 frontend, 21 browser end-to-end | done |
| Evaluation against hand-verified ground truth, dev/test split | done; **test set not run yet** |
| Template hints, a second model call for uncertain fields | not started |
| Records screen with date and sender filters; export | not started |
| Attach / split forms in the UI | not started (not needed by the samples) |
| Marking field positions on the image | not started (needs coordinates from the model) |
| Timing a 30-page batch, pre-processed demo results | not done (blocked by the daily quota) |

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

### Run the app

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
| Backend | `cd backend && python -m pytest` | pipeline rules, validation, database, API, quota handling, orientation (92 tests, SQLite) |
| Backend on PostgreSQL | `TEST_DATABASE_URL=postgresql+psycopg://hakaton:hakaton@localhost:5432/hakaton_test python -m pytest tests/test_repo.py` | the same database tests against the real engine. The database name must end in `_test`: these tests drop every table |
| Frontend unit and component | `cd frontend && npm test` | logic and behaviour in a simulated browser (98 tests) |
| Frontend type check and lint | `npx tsc -b` and `npx oxlint` | |
| Browser end-to-end | `cd frontend && npm run test:e2e` | the real frontend and real API in real Chromium: layout, zoom, the collapsible list, saving, confirming, approving, and sideways / upside-down scans (21 tests) |

The browser tests start their own servers (API on :8100, UI on :5174) with an in-memory database and a scripted vision model (`backend/e2e/server.py`). They never touch your data and never use API quota. First time only: `npx playwright install chromium`. Use `npm run test:e2e:ui` to watch them run. The six test pages are generated by `python -m e2e.make_fixtures` (run from `backend/`): a page's width selects the scripted answer, and a black marker block in one corner lets the scripted model tell whether a page is the right way up.

### Evaluating the model

This is the project's "eval": the same pages and ground truth, scored the same way, every time the model or prompt changes.

```bash
cd backend
python scripts/evaluate.py --provider gemini --split dev                  # calls the API, caches the answers
python scripts/evaluate.py --provider gemini --split dev --cached-only    # re-score from the cache, no API calls
python scripts/evaluate.py --provider gemini --pages p1_03 --no-orient    # measure what orientation correction adds
python scripts/diff_cache.py <cache-folder-name>                          # per-page disagreements with ground truth
```

For each field it reports accuracy, % flagged, and **errors that were not flagged** (the metric that matters most, because those reach the database unnoticed). Answers are cached in `data/eval_cache/<provider>-<model>-<prompt-hash>[-oriented]/`, so changing the prompt starts a fresh cache and re-scoring costs nothing. `data/split.json` reserves 14 pages as a **test set**: do not tune prompts on them. Results so far are in PLAN section 10.

## Data not in the repo

`data/pages/` (rendered page images), `data/storage/` (uploaded images) and the sample PDFs are git-ignored. Put the two sample PDFs in the repo root and, from `backend/`, run `python -m scripts.render_samples ../<part1>.pdf ../<part2>.pdf --out ../data/pages` to regenerate the images (it also writes `barcodes.json`). `data/ground_truth_draft.jsonl` (hand-verified from the yellow highlights), `data/split.json` and the evaluation cache are tracked.

## Assumptions

Learned from the samples rather than the task text (PLAN ADR-013):

- One record per form, holding lists of central numbers and commitment numbers.
- Central numbers are 6 digits, recognised by the word "מרכזי" near the sticker. A 6-digit number alone is not enough.
- If an institution sent the patient (hospital, lab, IDF…), it is the sender; otherwise the HMO.
- If a stamp date and a handwritten date differ, the stamp wins and the field is flagged with both values.
- Sample IDs are fake and many fail the check digit (13 of 48 have 8 or 10 digits). Flagging them is correct.
- The yellow highlight marks the wanted value, so the model reports `highlighted` and a highlighted candidate wins. This helps on the samples and does nothing on unmarked forms.

## Known limitations

- **Model quota.** The Gemini free tier allows **20 requests per day per model**. The provider walks a list of models (`GEMINI_FALLBACK_MODELS`), which gives roughly 80 a day, but accuracy across those models has not been compared, and some newer models answer slowly. A 40-form stack is possible only with fallbacks, and a real lab needs a paid tier or a local model. Pre-processed demo results remain the safety net.
- **Accuracy is not established.** The measured numbers cover 21 development pages (plus 2 sideways pages), on yellow-highlighted samples, so they are probably optimistic. The test set has not been run. Handwritten digits are often misread; they are flagged, not guessed.
- **Handwritten names are never trusted**: always flagged.
- Upside-down pages (180°) are detected only through the model's own flag, at the cost of one extra call per such page.
- Two forms on one page, and forms spanning several pages, are not supported (none exist in the samples).
- Groq is blocked on the development network, so the second provider has never been measured.
- No login, no schema migrations, one local server (PLAN ADR-005, ADR-011).

## Privacy

- Orientation, barcodes and image enhancement run locally.
- Only the page image is sent to the external model. Field values are not written to logs.
- On the free Gemini tier, inputs may be used by Google to improve products. That is acceptable for the altered sample data, **not** for real patient data. In a real lab, use a paid tier or a local model.
- Page images are meant to be deleted 30 days after approval (configurable; not implemented yet).
