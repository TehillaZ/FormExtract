"""Make one "smart memory" suggestion appear, for a demonstration. DEMO DATA: say so when you show it.

  python scripts/seed_suggestion_demo.py            # three earlier corrections, and a new form that gets the suggestion
  python scripts/seed_suggestion_demo.py --dry-run  # only say what would be made

A suggestion needs earlier corrections (PLAN ADR-023): the same reading, from the same sender, fixed the same way
at least 3 times. In a real lab those come from people's work. Here they are made through the real code: three
earlier forms are saved with the sender read wrongly (a hospital's name printed on a Meuhedet form) and corrected
by "a person" (the same patch the review screen uses), then a new form with the same wrong reading is read from a
sample page image. The suggestion on that form is computed by the real rule, not drawn. The sender is the field
where this helps: it comes from a closed list, so the same wrong reading really does repeat (numbers do not).
Every record is named "דמו" and its provider says "demo".

Needs data/pages (see the README). Writes into the database named in .env (DATABASE_URL), and one image into
data/storage. Safe to repeat: it does nothing if the demo forms are already there.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import repo  # noqa: E402
from app.db.session import init_db, session_scope  # noqa: E402
from app.evaluation import DATA  # noqa: E402
from app.pipeline.extract import build_record  # noqa: E402
from app.pipeline.process import process_page  # noqa: E402
from app.schemas import RawExtraction, RawValue as V  # noqa: E402
from app.services.demo_seed import ReplayProvider  # noqa: E402
from app.services.documents import register_upload  # noqa: E402
from app.storage import get_storage  # noqa: E402

WRONG = 'המרכז הרפואי ע"ש חיים שיבא - תל השומר'   # the hospital that printed the form, read as the sender
RIGHT = "מאוחדת"                                  # the HMO whose logo is highlighted: the real sender
PROVIDER = "demo (נתוני הדגמה)"
PAGE = "p1_01"   # an upright Meuhedet form whose printed provider is Sheba and whose highlighted sender is Meuhedet


def earlier_form(n: int) -> RawExtraction:
    return RawExtraction(
        template="meuhedet_commitment", sender=V(value="שיבא", source="printed"), other_senders=[V(value=RIGHT)],
        first_name=V(value="דמו", source="printed"), last_name=V(value=f"קודם {n}", source="printed"),
        id_numbers=[V(value="011223344", source="printed")],
        stamp_date=V(value="18/06/2026", source="stamp"),
        commitment_numbers=[V(value=f"71000000{n}", source="printed")])


def new_form() -> RawExtraction:
    raw = earlier_form(0)
    return raw.model_copy(update={"last_name": V(value="חדש", source="printed"),
                                  "commitment_numbers": [V(value="710000009", source="printed")]})


def already_seeded(db) -> bool:
    return any(r.provider == PROVIDER for r in repo.list_records(db, q="דמו", limit=50))


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="say what would be made, change nothing")
    args = ap.parse_args()
    image_file = DATA / "pages" / f"{PAGE}.png"
    if args.dry_run:
        print(f"would save 3 earlier forms, correct the sender {WRONG} -> {RIGHT} on each, and read {image_file.name} "
              f"as a new form with the sender {WRONG}")
        return

    init_db()
    with session_scope() as db:
        if already_seeded(db):
            print("The demo forms are already there. Nothing changed.")
            return
        for n in (1, 2, 3):
            rec = repo.save_record(db, build_record(earlier_form(n), [], provider=PROVIDER))
            repo.patch_record(db, rec.id, {"sender": RIGHT})
            repo.approve_record(db, rec.id)
        img = cv2.imread(str(image_file))
        img[0, 0] = img[0, 0] ^ 1           # a different file hash, so it is not seen as already uploaded
        ok, png = cv2.imencode(".png", img)
        doc, _ = register_upload(db, get_storage(), f"demo-{PAGE}.png", png.tobytes())
        page_id = doc.pages[0].id
    await process_page(page_id, (ReplayProvider(new_form(), PROVIDER), None))
    print(f"Done. Open the form 'דמו חדש': its sender ({WRONG}) has a suggestion to change it to {RIGHT}.")


if __name__ == "__main__":
    asyncio.run(main())
