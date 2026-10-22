"""Make one "smart memory" suggestion appear, for a demonstration. DEMO DATA: say so when you show it.

  python scripts/seed_suggestion_demo.py            # three earlier corrections, and a new form that gets the suggestion
  python scripts/seed_suggestion_demo.py --dry-run  # only say what would be made
  python scripts/seed_suggestion_demo.py --empty-sender   # the other case: a sender nobody read, filled in by hand

A suggestion needs earlier corrections (PLAN ADR-023): the same reading, from the same sender, fixed the same way
at least 3 times. In a real lab those come from people's work. Here they are made through the real code: three
earlier forms are saved with the sender read wrongly (a hospital's name printed on a Meuhedet form) and corrected
by "a person" (the same patch the review screen uses), then a new form with the same wrong reading is read from a
sample page image. The suggestion on that form is computed by the real rule, not drawn. The sender is the field
where this helps: it comes from a closed list, so the same wrong reading really does repeat (numbers do not).
The patients are fictional, and every record's provider says "demo" (it is demo data: say so).

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
PROVIDER_EMPTY = "demo, empty sender (נתוני הדגמה)"
PAGE = "p1_01"   # an upright Meuhedet form whose printed provider is Sheba and whose highlighted sender is Meuhedet


EARLIER = {0: ("דנה", "כהן"), 1: ("יעל", "אברהם"), 2: ("דוד", "מזרחי"), 3: ("מיכל", "לוי")}   # fictional patients
NEW = {False: ("רונית", "שמעוני"), True: ("אורי", "פרידמן")}   # by whether the sender is empty


def earlier_form(n: int, empty_sender: bool = False) -> RawExtraction:
    sender = V() if empty_sender else V(value="שיבא", source="printed")
    return RawExtraction(
        template="meuhedet_commitment", sender=sender, other_senders=[] if empty_sender else [V(value=RIGHT)],
        first_name=V(value=EARLIER[n][0], source="printed"), last_name=V(value=EARLIER[n][1], source="printed"),
        id_numbers=[V(value="011223344", source="printed")],
        stamp_date=V(value="18/06/2026", source="stamp"),
        commitment_numbers=[V(value=f"7{2 if empty_sender else 1}000000{n}", source="printed")])   # each demo has its own numbers


def new_form(empty_sender: bool = False) -> RawExtraction:
    raw = earlier_form(0, empty_sender)
    return raw.model_copy(update={"first_name": V(value=NEW[empty_sender][0], source="printed"), "last_name": V(value=NEW[empty_sender][1], source="printed"),
                                  "commitment_numbers": [V(value=f"7{2 if empty_sender else 1}0000009", source="printed")]})


def already_seeded(db, provider: str) -> bool:
    return any(r.provider == provider for r in repo.list_records(db, limit=500))


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="say what would be made, change nothing")
    ap.add_argument("--empty-sender", action="store_true",
                    help="the sender is not read at all on these Meuhedet forms, and people fill in Meuhedet by hand")
    args = ap.parse_args()
    empty, provider = args.empty_sender, PROVIDER_EMPTY if args.empty_sender else PROVIDER
    image_file = DATA / "pages" / f"{PAGE}.png"
    if args.dry_run:
        before = "empty" if empty else WRONG
        print(f"would save 3 earlier forms, correct the sender {before} -> {RIGHT} on each, and read {image_file.name} "
              f"as a new form with the sender {before}")
        return

    init_db()
    with session_scope() as db:
        if already_seeded(db, provider):
            print("The demo forms are already there. Nothing changed.")
            return
        for n in (1, 2, 3):
            rec = repo.save_record(db, build_record(earlier_form(n, empty), [], provider=provider))
            repo.patch_record(db, rec.id, {"sender": RIGHT})
            repo.approve_record(db, rec.id)
        img = cv2.imread(str(image_file))
        img[0, 0] = img[0, 0] ^ 1           # a different file hash, so it is not seen as already uploaded
        img[0, 1] = img[0, 1] ^ (2 if empty else 0)   # the two demos must not look like the same file either
        ok, png = cv2.imencode(".png", img)
        doc, _ = register_upload(db, get_storage(), f"demo-{PAGE}{'-empty' if empty else ''}.png", png.tobytes())
        page_id = doc.pages[0].id
    await process_page(page_id, (ReplayProvider(new_form(empty), provider), None))
    what = "its sender is empty" if empty else f"its sender ({WRONG})"
    print(f"Done. Open the form '{NEW[empty][0]} {NEW[empty][1]}': {what} and has a suggestion: {RIGHT}.")


if __name__ == "__main__":
    asyncio.run(main())
