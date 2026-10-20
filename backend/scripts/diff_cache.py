"""Show, per page, where the cached model answer disagrees with the ground truth (no API calls)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2  # noqa: E402
from app.evaluation import DATA, load_truth, score_record  # noqa: E402
from app.pipeline.barcodes import decode_barcodes  # noqa: E402
from app.pipeline.extract import build_record  # noqa: E402
from app.schemas import RawExtraction  # noqa: E402

cache = DATA / "eval_cache" / sys.argv[1]
truth = load_truth()
for f in sorted(cache.glob("*.json")):
    page = f.stem
    raw = RawExtraction.model_validate_json(f.read_text(encoding="utf-8"))
    bc = [b.text for b in decode_barcodes(cv2.imread(str(DATA / "pages" / f"{page}.png")))]
    rec = build_record(raw, bc)
    t = truth[page]
    for field, (ok, flagged) in score_record(rec, t).items():
        if ok:
            continue
        got = getattr(rec, field)
        got = [x.value for x in got] if isinstance(got, list) else got.value
        print(f"{page} {field:<19}{'FLAGGED' if flagged else 'SILENT '} got={got!r} want={t.get(field)!r}  [{t['template']}]")
