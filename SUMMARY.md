# FormExtract: summary

Written for: hackathon judges. A longer, technical account is in [PLAN.md](PLAN.md); how to run it is in [README.md](README.md).

## What it does

A lab receives scanned commitment forms (Hebrew, handwritten and printed, often crooked or sideways). A technician has to type first and last name, ID (ת"ז), central numbers, received date, sender and commitment numbers into a system. FormExtract does the reading; the technician does the checking.

1. Upload a PDF or image. Each page is turned upright and enhanced.
2. Barcodes are decoded locally (no model needed). One vision-model call reads the rest.
3. **Our code, not the model, decides how sure we are** of each value. Anything not clearly sure is flagged.
4. The technician sees the form next to the fields, confirms or corrects only the flagged ones, then approves.
5. Records are stored in PostgreSQL, searchable, and exportable to CSV or Excel.

The design rule: **the model may be wrong, but a wrong value must never look right.**

## How sure is "sure"

- A handwritten value is never trusted on its own.
- A number matching a barcode on the page is verified.
- An ID is "verified" only if its check digit passes **and** a second reading or a highlight corroborates it. Before this rule, a "verified" ID was wrong 37% of the time.
- Saving a flagged field unchanged counts as a human confirmation, and is recorded as such.

## Honest numbers

The metric that matters is **errors that were not flagged** ("silent errors"): the ones a technician would never look at.

| Run | Pages | ID correct | Date correct | Silent errors |
|---|---|---|---|---|
| Gemini 2.5 Flash, development pages | 21 | 7 | 12 | 2 (both ID) |
| Gemini 2.5 Flash, **held-out test pages** | 11 of 14 | 5 | 4 | 1 (sender) |
| Groq Qwen 3.8, development pages | 31 | 6 | 14 | 5 |

Reading: on the test pages, 1 error in 55 field values slipped through unflagged; the other wrong values were flagged for a human. Most values are flagged, which is the intended trade: the tool saves typing and looking things up, but it does not remove the check.

Caveats we state in the app itself:
- The test set was run on **11 of 14 pages** (the daily free-tier quota ran out). The three missing pages were not tuned on and can be added without changing any rule.
- The sample forms are highlighted; real forms are not. Accuracy on unmarked forms is not measured.
- Gemini vs. Groq was compared on the same 16 pages: the difference is not statistically significant.
- Small samples. These are indications, not guarantees.

## What is built

Backend (FastAPI, SQLAlchemy, PostgreSQL), frontend (React, TypeScript, Hebrew RTL), a review screen with keyboard shortcuts (↑↓ forms, N next to review, A approve a clean form, L list), a records table with search/filter/export, an accuracy screen with side-by-side model comparison, and a one-command start. Tests: backend 221, frontend 202, browser (Playwright) 40, all passing.

## What a real lab would still need

- A paid model tier or a local model (the free tier allows 20 requests per day per model).
- Login and roles; the data is personal and health-related.
- A retention policy, audit trail, database migrations, backups.
- Accuracy measured on the lab's own unmarked forms, and on far more than 48 pages.

---

## Demo rehearsal checklist

Before: run `./start.ps1` (or `start.sh`), then `python backend/scripts/seed_demo.py` on a **fresh** database. It replays saved model answers through the real pipeline (44 pages, labelled "(saved answer)"), so no quota or network is needed. Say out loud that these are saved answers.

Flow (about 4 minutes):
1. **Table**: totals, "N fields need review". Point at a flagged cell.
2. **Review a form**: image next to fields; show "נקרא: …" for a rejected value. Press `N` (next to review), `↓`.
3. **Correct** one field, **confirm** another with ✓. Press `A` on a form with flags: it refuses and says why. Confirm all, press `A`: approved, moves on.
4. **Duplicate commitment number**: approving a second form with the same number is refused.
5. **Sideways scan**: open one; it was turned upright automatically.
6. **Records / export**: filter, export Excel (RTL).
7. **Accuracy screen**: the table above; point at "errors not flagged" and at the warning that the test set ran on 11 of 14 pages.
8. **Close** with the limitations list.

If something fails: the seeded demo needs no model, so the table, review, approve, export and accuracy screens all still work. Only a live upload needs a model key.
