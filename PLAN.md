# PLAN — Commitment-Form Extraction Engine (Central Virology Laboratory)

> Living design document. Items marked **[OPEN]** are waiting for a decision. Decisions that were made are recorded in the "Architecture decisions" section (ADRs). The UI is Hebrew and right-to-left; this document is in English. Hebrew terms that appear on the forms themselves (field labels, sender names, UI messages) are kept as written.

---

## 1. Goal

The central virology laboratory receives commitment forms in many formats: printed, scanned, photographed and handwritten. Today they are typed in by hand. The system accepts one form or a stack, extracts the required fields, marks where it is not sure, and lets the lab technician correct and approve. Records are stored in a database.

**Guiding principle:** an empty, flagged field is always better than a guessed value. The system is measured not only by how often it is right, but by how well it knows when it is wrong.

**Success scenario from the requirements:** upload 30 forms, get a full table with 3 fields marked orange, fix them and approve. The whole thing takes 4 minutes instead of an hour.

---

## 2. Fields to extract

| Field | Notes from the samples |
|---|---|
| First name | Mostly handwritten. The order of first and last name varies between forms |
| Last name | Same |
| ID number (ת"ז) | Normalized to 9 digits. The check digit is validated, but the sample IDs were altered and may fail it (see ADR-014) |
| Central number (list) | Per the PDF: a sticker marked "מרכזי", sometimes handwritten. There may be several; all are kept. **Assumption from the samples:** barcode and 6 digits. There are distractors: 6-digit numbers that are not central numbers |
| Received date | A "התקבל" stamp, or handwriting below the central number. Distractors: birth date, print date, expiry date |
| Sending party | A closed list (source in section 5.4). When both an HMO and a hospital appear, the samples highlight the hospital |
| Commitment number (list) | Per the PDF: also appears as "דרישה", and at Leumit as "דגימה". **From the samples:** also "אסמכתא". 4 to 12 characters, sometimes with a letter. There may be several; all are kept |

**A field that is not found:** the value is empty, and the field is always flagged for review with the reason "לא נמצא" (not found). A default value is never filled in.

---

### 2.1 Findings from the samples (day 1)
A ground-truth table for all 48 pages is in `data/ground_truth_draft.jsonl`, built from the highlights and verified by hand.

- **Orientation:** 11 pages are rotated by 90 degrees. 23 pages are skewed by a small angle (up to 5 degrees), which deskewing handles.
- **Central number:** 53 numbers, all 6 digits. 41 can be decoded from the barcode. The rest are handwritten (hospital screenshots) or have a barcode that did not decode. 4 pages have 2 or 3 central numbers.
- **6 digits is not enough to identify a central number:** at Bnei Zion the commitment number is 6 digits with a barcode. Identification must rely on the word "מרכזי" next to the sticker.
- **Commitment number:** 4 to 12 characters. Some have a letter prefix (X132767) and some a leading zero (03240), so it is stored as a string. 2 pages have several numbers, and 7 pages have none (Rosenblatt, Ichilov, Forensic Medicine, Tzafon). Sometimes it is handwritten in another field, and sometimes it is called "מספר מבחנה", "מס' דגימה", "אסמכתא" or "דרישה".
- **Received date:** a "התקבל" stamp, or handwriting below the central number or inside an empty stamp. A recurring distractor: "ת.קבלה" on the hospital sticker, which is the hospital admission date and not the lab receipt date.
- **Sending party:** besides HMOs and hospitals there is also a private lab (Rosenblatt), the IDF, the Ministry of Defense, MDA, the Palestinian Authority and the National Center for Forensic Medicine. When both an HMO logo and a hospital appear, the hospital is usually the highlighted one. Distractor: "גורם שולח: בית ג'אן" on a Leumit form, which is not the sending party.
- **ID:** usually appears two or three times on a page (sticker and handwriting), so the readings can be compared. On two pages the original name and ID are erased and rewritten.

## 3. What the system includes (MVP)

1. Upload of one or several files (PDF, JPG, PNG, iPhone HEIC). Both a single form and a stack.
2. Splitting into forms (ADR-015): by default page = form, and the model flags a page that continues the previous one. Manual buttons "attach to previous form" / "split".
3. Image enhancement: perspective correction for phone photos, deskewing for skewed scans, contrast enhancement for dark scans.
4. Page orientation detection and automatic rotation.
5. Form template recognition (sender and form type: Clalit, Leumit, hospital, etc.).
6. Barcode decoding.
7. Field extraction with a vision model and structured output.
8. Normalization, validation and a confidence score per field.
9. Review screen: the form image next to the fields, orange highlighting of whatever is uncertain with an explanation, in-place correction and approval.
10. Records screen: search, and filtering by status, date and sender.
11. Duplicate detection (same file or same central number) with a warning.
12. Correction log: what changed, from which value to which, and when. No user identity, since there is no login in the MVP (ADR-011).
13. Documented REST API (OpenAPI) for future integration with the lab system.
14. Evaluation script against the ground truth, computing accuracy per field.

---

## 4. User interface

The whole UI is in Hebrew and right-to-left.

### 4.1 Upload screen
- A large drag-and-drop area with a "בחרי קבצים" (choose files) button.
- After upload, a file list appears with a status for each page: waiting, processing, ready or error.
- Automatic move to the review table when processing finishes, or a "לבדיקה" (to review) button.

### 4.2 Review table (the main screen in the demo)
- A row per form and a column per field.
- An uncertain cell has an orange background. Hovering shows the reason, for example "ספרת ביקורת לא תקינה" (invalid check digit) or "כתב יד" (handwriting).
- An empty cell (not found) is marked so that it is clear it is empty on purpose.
- A counter at the top: "30 טפסים · 3 שדות דורשים בדיקה" (30 forms, 3 fields need review).
- Quick filter: "show only rows with fields to review".
- A button "אשרי את כל השורות התקינות" (approve all clean rows).

### 4.3 Single-form screen
- On the right, the form image, with zoom and manual rotation.
- On the left, the fields, each with its value, a confidence badge and the reason.
- In-place editing. The list fields (central, commitment) can be added to and removed from.
- Navigation between forms: previous, next, and next one that needs review.
- A button "אשרי ושמרי" (approve and save).

### 4.4 Records screen
- All records in the system, from all uploads.
- Search by ID, central number or commitment number.
- Filter by status (pending or approved), received date and sender.
- Export of the filtered result (an extra, see section 9).

---

## 5. How it works — the processing pipeline

```
file
 → convert to images (PDF via PyMuPDF, HEIC via pillow-heif)
 → local image enhancement (OpenCV): perspective, deskew, contrast
 → local orientation detection (Tesseract OSD) + rotation
 → local barcode decoding
 → one model call: template + "continuation of the previous page?" + field extraction (general prompt + template hints)
 → split / merge pages into forms
 → normalization
 → validation + confidence score
 → [second call only for uncertain fields: consistency check]
 → save to DB (status: pending)
```

**Call budget:** one call per page, plus another call only for pages with uncertain fields. For 30 pages that is about 30 to 45 calls instead of 90. Everything that can be done locally (orientation, barcode, image enhancement) costs no call.

### 5.0 Image enhancement
- **Phone photo:** detect the four corners of the sheet (contours) and correct perspective. If the corners are not found, continue with the original image.
- **Skewed scan:** deskew by the angle of the text lines, up to about 15 degrees.
- **Dark scan:** CLAHE for contrast enhancement.
- The original image is also kept, and the review screen shows it.
- If the image is still unreadable (for example very blurry), all fields are flagged with the reason "איכות תמונה נמוכה" (low image quality).

### 5.1 Template hints
A configuration file (YAML or JSON) per template, describing where each field is and how it is called. For example:
- Rambam: "the sample number is the commitment number".
- Leumit: "the commitment number appears as 'דגימה'".
- Maccabi (lab form): "the commitment number appears as 'דרישה'".

This allows adding a new template without changing code. If the template is not recognized, only the general prompt is used.

### 5.2 Confidence rules

| Level | When |
|---|---|
| High | There is external verification: a matching barcode, an ID that passes the check digit (only in `strict` mode, see ADR-014), or an exact match of the sender to the list |
| Medium | The reading is consistent but unverified |
| Low | A check failed: inconsistent readings, an implausible date, a central number that is not 6 digits (for example a cropped sticker), a sender not in the list, an unverified handwritten value, low image quality, or a field that was not found |

Medium and low are shown in orange. The confidence score the model gives itself is used at most as an extra signal, never as the basis.

### 5.3 Validations
- ID: pad to 9 digits. The check digit depends on the `ID_CHECKSUM_MODE` mode (ADR-014).
- Received date: not in the future, and not before other dates on the form (a soft check).
- Central number: 6 digits (an assumption from the samples), compared with the barcode if one is found.
- Sending party: fuzzy match against the closed list. If there is no match, the value stays empty, the text that was read is kept in `raw_text` and shown in the explanation, and the field is flagged.

### 5.4 Sender list
- HMOs: Clalit, Maccabi, Meuhedet, Leumit.
- Hospitals: a list of 45 hospitals received from a team member, matching the list of hospitals in Israel on Wikipedia (https://he.wikipedia.org/wiki/בתי_חולים_בישראל), per the guidance in the PDF.
- 6 parties found in the samples were added: Rosenblatt, the IDF, the Ministry of Defense, MDA, the Palestinian Authority and the National Center for Forensic Medicine.
- The file: `backend/app/data/senders.json` (55 parties), with a category and alternative names for each (for example "רמב"ם" / "רמבם" / "Rambam"). Matching is in `app/validation/senders.py`: an exact match on the name or alias first, otherwise a fuzzy match. A fuzzy match lowers confidence to medium.
- The source and the retrieval date are documented in the README. The list can be extended without code.

---

## 6. Data model (draft)

```python
class Field(BaseModel):
    value: str | None          # None = not found, never guessed
    raw_text: str | None       # what was read before normalization (e.g. sender not in list)
    confidence: Literal["high", "medium", "low"]   # value None -> always "low", reason "לא נמצא"
    source: Literal["printed", "handwritten", "sticker", "stamp", "barcode", "manual"] | None
    reasons: list[str] = []

class Correction(BaseModel):
    field: str
    old_value: str | None
    new_value: str | None
    at: datetime               # no user identity in MVP (ADR-011)

class CommitmentRecord(BaseModel):
    id: UUID
    document_id: UUID
    page_numbers: list[int]
    template: str | None
    first_name: Field
    last_name: Field
    id_number: Field
    central_numbers: list[Field]
    received_date: Field
    sender: Field
    commitment_numbers: list[Field]
    status: Literal["pending", "approved"]
    corrections: list[Correction]
```

Main tables: `documents` (the uploaded file), `pages`, `records`, `record_commitment_numbers` (ADR-016), `record_central_numbers`, `corrections`. The sender list is a JSON file.

---

## 7. API (draft)

| Method | Path | Description |
|---|---|---|
| POST | `/documents` | Upload one or several files |
| GET | `/documents/{id}` | Processing status |
| GET | `/records` | List records with filtering (`status`, `sender`, `from`, `to`, `q`, `needs_review`, `document_id`) |
| GET | `/records/{id}` | A single record |
| PATCH | `/records/{id}` | Correct fields |
| POST | `/records/{id}/merge-previous` | Attach the form to the previous form |
| POST | `/records/{id}/split` | Split a form by page |
| POST | `/records/{id}/approve` | Approve |
| POST | `/records/approve-clean` | Approve all pending records with nothing flagged |
| POST | `/pages/{id}/reprocess` | Retry a failed page |
| GET | `/pages/{id}/image` | The page image |
| GET | `/senders` | The closed sender list |
| GET | `/export` | Export (extra) |

---

## 8. Technology

| Layer | Choice |
|---|---|
| Backend | Python, FastAPI |
| Schemas | Pydantic (also for the model output) |
| PDF to image | PyMuPDF, and pillow-heif for HEIC images |
| Image processing | OpenCV (perspective, deskew, CLAHE) |
| Barcodes | zxing-cpp (to be tested on the samples) |
| Vision model | One primary provider on a free tier and a fallback provider from another vendor, behind a swappable provider interface (ADR-003) |
| Secondary OCR | Tesseract with Hebrew, also for orientation detection (OSD) |
| DB | PostgreSQL (ADR-004) |
| ORM | SQLAlchemy |
| Background processing | FastAPI BackgroundTasks, status in the DB (ADR-005) |
| Image storage | Local disk, path in the DB, behind a storage interface (ADR-006) |
| Frontend | React, TypeScript, Vite |
| Styling | Tailwind, with `dir="rtl"` and logical classes (ADR-007) |
| Data fetching | React Query |
| Running | Local Docker Compose. Cloud later |
| Tests | pytest, and the evaluation script |

---

## 9. Extra features (in priority order)

1. Export the filtered result to CSV or Excel.
2. An "accuracy report" screen: the evaluation script results in the UI, accuracy per field.
3. Marking the field location on the image. Start with barcodes, for which zxing-cpp returns an exact position. Coordinates from the vision model only if time remains and they prove reliable.
4. A "highlight removal" mode: remove the yellow marker from the image, to measure accuracy under conditions close to the field.
5. Running a local model instead of an external API.
6. Keyboard shortcuts in the review screen (Enter to approve, Tab to the next field that needs review).
7. Statistics: how many forms today, how many corrections by field and by sender.

(Merging and splitting pages moved to the MVP, see ADR-015.)

---

## 10. Measurement

- A ground-truth table in JSON for all pages, built from the highlights in the samples and verified by hand.
- Split: development pages, and 12 to 15 test pages that are not touched while writing prompts (`data/split.json`).
- Metrics per field: accuracy, percentage flagged, and percentage of errors that were not flagged. The last one is the most important metric.
- In the honest report: the samples are marked with a highlighter, so accuracy on them is probably higher than in reality.

---

## 11. Privacy

- Local first: orientation, barcodes and image enhancement run locally, with nothing sent out.
- Only what is needed for extraction is sent to the external model. The fallback provider receives a page only when the primary one fails, so as not to spread the information between providers unnecessarily.
- Field values are not written to logs.
- Only the required fields and the page image are stored.
- Images are deleted automatically 30 days after the record is approved. The value is configurable. The record itself stays.
- On the Gemini free tier, the input may be used to improve Google products. That is acceptable in development on samples whose details were altered, but not in the field. The summary should state: in the field, only a paid tier or a local model.
- The summary should state what is needed to run the system in the lab without sending information out.

---

## 12. Architecture decisions

> Decisions that were made are recorded here. Template for each decision:

```
### ADR-NNN: Title
- Date:
- Context: what the problem is
- Options considered:
- Decision:
- Rationale:
- Consequences:
```

### ADR-001: Python and FastAPI for the backend
- Context: PDF and image processing, and widening the stack beyond .NET.
- Decision: Python with FastAPI.
- Rationale: the document-processing libraries are written for Python first. Prior experience with Pydantic.

### ADR-002: Records are stored in the DB, export to a file on demand
- Context: clarification from the organizers that Excel is not the goal and that there will eventually be an API.
- Decision: one source of truth in the DB. Exports are generated from it on demand.

### ADR-003: A swappable vision-model provider, chosen by experiment
- Context: a Claude subscription does not include an API, and the development budget is zero.
- Decision: one `VisionProvider` interface with two free implementations: Gemini (Google AI Studio) and Groq (open models with image support). On day 1 both are run on the same 5 to 10 pages from the ground-truth table. The better one is the primary provider and the other is the fallback. The provider can be changed through an environment variable.
- **Fallback chain:** one key per provider. When the primary returns 429 even after backoff, the page goes to the fallback provider, and this is recorded in the record (`provider`) so it is clear which model did the extraction.
- **Not done:** several keys or accounts at the same provider to get around the rate limit. This goes against the terms of service of most providers and could cause a block on demo day.
- **[OPEN]**: the result of the experiment, and timing a stack of 30 pages. Status: only Gemini has been measured. Groq is blocked by the current network filter (NetFree, HTTP 418), so the comparison has to be run from another network.
- Consequences: low rate limits, which means limited parallel processing and handling of 429 errors. On the free tier the input may be used by the provider (see section 11). Two providers may give different accuracy, so evaluation reports each provider separately.
- **Demo backup:** the demo stack is processed in advance and saved in the DB. If there is a rate limit during the demo, the saved results are shown.

### ADR-004: PostgreSQL
- Rationale: familiar, and suitable for a future cloud deployment with managed PostgreSQL.

### ADR-005: Background processing with BackgroundTasks, and polling from the UI
- Context: processing a stack takes time, and the UI needs to update.
- Decision: the upload returns a document ID at once. Processing runs in BackgroundTasks, and the status of each page is stored in the DB. React Query polls every 2 to 3 seconds until processing finishes.
- Rationale: no Redis and no separate worker. Fits the scale of a hackathon.
- Consequences: work in the middle of processing is lost if the server crashes, so a "reprocess" button is needed for a failed page. A cloud deployment requires a continuously running server, not serverless.

### ADR-006: Images on disk, path in the DB, behind a storage interface
- Rationale: the DB stays light. A `Storage` interface allows switching to cloud storage later without changing the rest of the code.

### ADR-007: Tailwind with RTL
- Decision: `dir="rtl"` at the page level, and logical classes (`ms-`, `me-`, `ps-`, `pe-`, `start-`, `end-`) instead of left and right.

### ADR-008: Limited parallel processing
- Decision: an `asyncio.Semaphore` with a low default (2), configurable, a minimum interval between calls to one provider, and retry with backoff on 429 errors.

### ADR-009: Orientation detection in two stages
- Decision: Tesseract OSD, which is local, free and fast, rotates before the model call. The single model call also returns "does the text look upside down". If so, the page is rotated 180 degrees and sent again. This is the only case where a page costs an additional call because of orientation.
- Status: Tesseract is not installed yet. Until then, only the model's upside-down flag is available.

### ADR-010: Duplicates
- Decision: an identical file hash is a certain duplicate, and the file is not processed again. A central number that already exists in the DB raises a warning on the record, but does not block.

### ADR-011: One user, no login in the MVP

### ADR-012: Development and demo run locally in Docker, cloud later
- Consequences: configuration through environment variables. The frontend can move to Vercel. The backend needs a service that runs a server continuously (ADR-005).

### ADR-013: Working assumptions from the samples (will appear in the README under "Assumptions")
- **Several commitment numbers:** one record per form, with a list of numbers. Splitting into separate records is a small API change, if needed.
- **Sending party:** if a sending institution appears, it is the sending party. Otherwise the HMO. In the hospital-system screenshots this is the field "גורם מפנה". Based on the highlights in the samples.
- **Closed list:** the categories are HMO, hospital, lab and government body, and can be extended without code (source in section 5.4). According to the samples the list also includes Rosenblatt, the IDF, the Ministry of Defense, MDA, the Palestinian Authority and the National Center for Forensic Medicine. A sender that is not in the list stays empty, the text that was read is shown in the explanation, and the field is flagged.
- **Stamp versus handwritten date:** if they are identical, high confidence. If they differ, the stamp is chosen, the field is flagged, and both values appear in the explanation.
- **Hospital-system screenshots:** treated as a form type, since they are in the lab's samples.
- **A 6-digit central number with a barcode:** learned from the samples, it is not written in the PDF.
- **"דרישה" / "דגימה" / "אסמכתא":** the PDF says "דרישה" in general and "דגימה" for Leumit. The assignment to other templates (for example Maccabi, Rambam) and "אסמכתא" were learned from the samples.
- **Highlighted values:** the model reports which values are covered by a yellow marker. When candidates compete, the highlighted one wins. This helps on the samples, and does nothing on unmarked forms.
- **Barcode match:** a barcode match proves a number is on the page, not that it is the wanted one. With competing candidates, an unhighlighted barcode match is only medium.

### ADR-014: ID check digit
- Context: according to the PDF, the ID numbers in the samples were altered and are not real people's. They may fail the check digit, in which case the confidence rule would flag almost every ID.
- Decision: an environment variable `ID_CHECKSUM_MODE`:
  - `strict` (default for the field): passes = high confidence, fails = low with the reason "ספרת ביקורת לא תקינה".
  - `lenient` (for the samples): the check does not change confidence. Confidence is set by reading consistency and handwriting type, and the result is shown only as information in the explanation.
- On day 1, check how many IDs in the ground-truth table pass the check. If most fail, the demo and evaluation run in `lenient`.
- **Result (day 1):** 35 of 48 pass, because the common fake value 11223344 happens to be valid. The 13 that fail are written with 8 or 10 digits (for example 0011223344), so flagging them is correct. **The demo and evaluation run in `strict`.**
- In the honest report: state which mode the evaluation ran in, and that in the field the check is enabled and will improve ID error detection.

### ADR-015: Splitting into forms
- Context: the PDF defines "split forms" as the first step. One PDF file contains many forms, and a form may span two pages.
- Decision: by default page = form. The model call also returns "is the page a continuation of the previous one" (for example no form title and no identification fields). If so, the page is attached to the previous record and the fields are merged. The UI has buttons "צרפי לטופס הקודם" (attach to previous form) and "פצלי" (split).
- On day 1, go through the samples and check whether there are multi-page forms or two forms on one page. Two forms on one page are not supported in the MVP and will be listed under limitations.
- **Result (day 1):** the samples contain no multi-page form and no two forms on one page. Two pages say "עמוד 1 מתוך 2", but the next page is a different form. So page = form, and continuation detection remains only as a safety net. "Page 1 of 2" must not be relied on as a sign of continuation.

### ADR-016: Primary key and uniqueness of the commitment number
- Context: the commitment number is supposed to be unique, but 7 of 48 pages do not have it, and sometimes it is unreadable. In addition, the central system may receive data from more sources. (Feedback from the organizers.)
- Decision:
  - Primary key: an `id UUID` for every record, independent of the commitment number.
  - The commitment numbers live in a child table `record_commitment_numbers(record_id, value, status)`, because a record may have several (ADR-013).
  - A partial unique index: `CREATE UNIQUE INDEX ... ON record_commitment_numbers (value) WHERE status = 'approved'`. An empty number is never stored, so it is never counted as a duplicate.
- Note: the index applies only to **approved** records. Pending records with a number that already exists are not blocked but get a duplicate warning (ADR-010), so the technician can see and decide. Approving a record with an already-approved number is rejected with a clear message (HTTP 409).
- **[OPEN]**: can the same commitment number appear in two valid records (for example two forms for the same sample)? To ask the organizers.
- Consequences: `status` is copied to the child table and must stay in sync with the record.

---

## 13. Open questions

### Technical
1. **Which Gemini model?** Two or three models should be compared on 5 to 10 handwritten pages, within the free-tier limits. Status: `gemini-2.5-flash` measured. A second model (for example flash-lite) is untested, and its quota may be separate.
2. **Rate limits on the free tier:** are they enough to run a stack of 30 pages in a reasonable time in the demo? Measured so far: about 20 pages per session on Gemini before the quota stops it. With one call per page and a fallback provider (ADR-003) the chances are good, and there are also pre-saved results.
3. **ID check digits in the samples:** do the IDs in the samples pass? Settled: 35 of 48 pass (ADR-014).
4. **Multi-page forms:** are there any in the samples? Settled: no (ADR-015).
5. **Cloud deployment:** which service for the backend and PostgreSQL. To be decided after submission.
6. **Schema migrations:** there is no Alembic yet. A schema change currently needs a reset of the dev database.

### For the organizers
1. Does the hackathon provide credits for model APIs?
2. Can the same commitment number appear in two valid records? (ADR-016)

---

## 14. Schedule (two days)

### Day 1
- [x] Project setup: folder structure (backend, venv, requirements, .gitignore, .env.example)
- [~] Docker Compose and DB (compose file and DB code exist and pass tests on both SQLite and PostgreSQL 16)
- [~] One API key for Gemini and one for Groq (keys are in `.env`; Groq is blocked on the current network)
- [x] Ground truth: draft for all 48 pages
- [x] Ground truth: manual verification
- [x] Checks on the samples: ID check digits (ADR-014), multi-page forms (ADR-015), barcodes (section 2.1)
- [x] Seed of the sender list and matching to it (section 5.4)
- [x] PDF and HEIC conversion to images, barcode decoding, image enhancement (perspective, deskew, contrast)
- [ ] Orientation detection and rotation (needs Tesseract with Hebrew installed)
- [~] Basic extraction in one call with structured output, and a comparison experiment between the two providers (Gemini measured on 21 dev pages; Groq not yet)
- [x] Normalization and validations
- [x] Save to DB and basic API (FastAPI: upload, status, records, patch, approve, approve-clean, images)
- [ ] Timing a stack of 30 pages
- [x] First run of the evaluation script (partial, because of the Gemini rate limit)

### Day 2
- [ ] Template hints for the main senders
- [~] Confidence calculation (done) and a second call for uncertain fields (not done)
- [~] Fallback provider on a 429 (implemented and tested with a fake provider; not tried against Groq)
- [x] Upload screen
- [~] Review table and single-form screen (done; attaching and splitting forms not yet)
- [ ] Records screen with filtering (the form list has search and a needs-review filter; date and sender filters and export are not built)
- [~] Duplicate detection (hash and warnings done; UI not done)
- [ ] Running the evaluation on the test set
- [~] README (written), run instructions and summary (approach, limitations, what the lab needs)
- [ ] Pre-processing the demo stack and saving it in the DB (backup for the rate limit)
- [ ] Rehearsing the demo scenario

---

## 15. Risks

| Risk | Mitigation |
|---|---|
| Hebrew handwriting is not read | Flag and do not guess. The names in the samples are scribbles anyway |
| Barcodes do not decode in a scan | An extra signal only, the system does not depend on it |
| API rate limits or cost | One call per page, limited parallel processing, a fallback provider, and pre-saved results for the demo |
| IDs in the samples fail the check digit | Settled: `strict` mode is kept (ADR-014) |
| Skewed phone photos or dark scans | Local image enhancement, and fields flagged when quality is low |
| Overfitting to the samples | Separation between a development set and a test set |
| Not enough time for the UI | The review table comes before any other screen |
| The only measured provider is rate limited and the second is blocked on this network | Test a second Gemini model, or run the Groq comparison from another network; pre-saved demo results |
