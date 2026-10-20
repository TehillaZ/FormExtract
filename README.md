# FormExtract — commitment-form extraction engine

Extracts the required fields from Hebrew lab commitment forms (printed, scanned, photographed or handwritten) with a vision model, **flags every value it is not sure about**, and stores approved records in a database behind a REST API.

Guiding principle: an empty, flagged field is always better than a guessed value. The system is judged not only by how often it is right, but by how well it knows when it is wrong.

> Design, decisions (ADRs) and the day-by-day checklist live in [PLAN.md](PLAN.md) (English; the UI itself is Hebrew).

## Status

Work in progress (hackathon). See the checklist in section 14 of the plan.

| Area | State |
|---|---|
| PDF / image / HEIC ingest, perspective fix, deskew, contrast | done |
| Barcode decoding (zxing-cpp) | done |
| Closed sender list + fuzzy matching (55 senders) | done |
| ID normalization and check digit (`strict` / `lenient`) | done |
| Vision providers (Gemini, Groq) behind one interface, 429 backoff, call throttling | code done; only Gemini measured so far |
| Extraction, normalization, per-field confidence and reasons | done |
| Evaluation script against hand-verified ground truth, dev/test split | done |
| Database layer (SQLAlchemy): save, search, correct, approve, duplicates | done, tested on SQLite only |
| REST API (FastAPI), background processing | not started |
| Orientation: sideways pages turned locally, upside-down pages flipped after a model check (no Tesseract needed) | done; effect on accuracy measured on 2 pages only |
| Provider fallback on 429, template hints, second look at uncertain fields | not started |
| Frontend: upload, review table, single-form review screen (collapsible form list, zoom, lens, expanded view, inline editing) | done, first version |
| Frontend: records screen with date/sender filters, export | not started |
| Marking field locations on the image (needs coordinates from the model) | not started |

## How it works

```
file → page images → local image enhancement → local barcodes
     → one vision-model call per page (structured JSON)
     → normalization + validation + confidence → DB (status: pending)
     → human review (orange = needs a look) → approve
```

Confidence is **not** taken from the model. It is computed by our code (`backend/app/pipeline/extract.py`):

- **high**: independently verified, e.g. barcode match, ID passing the check digit (strict mode), exact sender-list match.
- **medium**: consistent reading with no verification.
- **low**: failed a check, handwritten and unverified, inconsistent reads, or not found. A missing field stays empty and is flagged "not found".

Anything not `high` is shown in orange for review. Human corrections are logged (old value, new value, time).

Commitment numbers: each record has its own UUID key, so a missing number is fine. Approved records may not share a commitment number (partial unique index); duplicates among pending records are only a warning (PLAN ADR-010, ADR-016).

## Setup

Developed on Python 3.14; any recent Python 3 should work (not tested on others).

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # Windows; use .venv/bin/pip on Linux/macOS
cp ../.env.example ../.env                          # then fill in GEMINI_API_KEY and/or GROQ_API_KEY
.venv/Scripts/python -m pytest -q
```

Database (PostgreSQL 16): `docker compose up -d db` from the repo root. Tests use in-memory SQLite.

### Run the app

```bash
# terminal 1: API on :8000 (needs the database above and a vision key in .env)
cd backend && .venv/Scripts/python -m uvicorn app.api.main:app --port 8000

# terminal 2: UI on :5173 (proxies /api to the API)
cd frontend && npm install && npm run dev
```

Open http://localhost:5173, upload forms in the "העלאה" tab, then review them in "טבלה" or "טופס". Frontend checks: `npm test`, `npx tsc -b`, `npm run build`.

### Evaluation

```bash
cd backend
python scripts/evaluate.py --provider gemini --split dev            # calls the API, caches answers
python scripts/evaluate.py --provider gemini --split dev --cached-only
python scripts/diff_cache.py <cache-folder-name>                    # per-page disagreements with ground truth
```

For each field it reports accuracy, % flagged, and **errors that were not flagged** (the metric that matters most). Answers are cached in `data/eval_cache/<provider>-<model>-<prompt-hash>/`, so changing the prompt starts a fresh cache and re-scoring costs nothing. `data/split.json` reserves 14 pages as a **test set**: do not tune prompts on them.

## Data not in the repo

`data/pages/` (rendered page images) and the sample PDFs are git-ignored. Put the two sample PDFs in the repo root and, from `backend/`, run `python -m scripts.render_samples ../<part1>.pdf ../<part2>.pdf --out ../data/pages` to regenerate the images (it also writes `barcodes.json`). `data/ground_truth_draft.jsonl` (hand-verified from the yellow highlights), `data/split.json` and the evaluation cache are tracked.

## Assumptions

Learned from the samples rather than the task text (PLAN ADR-013):

- One record per form, holding lists of central numbers and commitment numbers.
- Central numbers are 6 digits, recognised by the word "מרכזי" near the sticker. A 6-digit number alone is not enough.
- If an institution sent the patient (hospital, lab, IDF…), it is the sender; otherwise the HMO.
- If a stamp date and a handwritten date differ, the stamp wins and the field is flagged with both values.
- Sample IDs are fake and many fail the check digit (13 of 48 have 8 or 10 digits). Flagging them is correct.

## Known limitations

- The Gemini free tier allows **20 requests per day per model**. The provider walks a list of models (see `GEMINI_FALLBACK_MODELS`), which gives roughly 80 a day, but accuracy across those models has not been compared. Groq is blocked on the development network. Pre-processed demo results remain the safety net.
- Handwritten names are never trusted: always flagged.
- Two forms on one page, and forms spanning several pages, are not supported (none exist in the samples).
- Accuracy numbers are on yellow-highlighted samples and are probably optimistic compared to real forms.
- Upside-down pages (180°) are only detected through the model's own flag, at the cost of one extra call per such page.

## Privacy

- Orientation, barcodes and image enhancement run locally.
- Only the page image is sent to the external model. Field values are not written to logs.
- On the free Gemini tier, inputs may be used by Google to improve products. That is acceptable for the altered sample data, **not** for real patient data. In a real lab, use a paid tier or a local model.
- Page images are meant to be deleted 30 days after approval (configurable; not implemented yet).
