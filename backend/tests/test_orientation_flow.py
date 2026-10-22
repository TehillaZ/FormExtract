"""The upside-down retry (ADR-009): flip and ask again, but never ping-pong and never pay twice for an upright page."""
import numpy as np

from app.pipeline.process import extract_oriented
from app.schemas import RawExtraction


class ScriptedProvider:
    """Answers `upside_down` flags from a script, one per call."""

    name = "scripted"

    def __init__(self, *flags: bool):
        self.flags, self.calls, self.seen = list(flags), 0, []

    async def extract(self, img, hint=""):
        self.seen.append(img)
        flag = self.flags[min(self.calls, len(self.flags) - 1)]
        self.calls += 1
        return RawExtraction(text_upside_down=flag)


def marked_page() -> np.ndarray:
    img = np.zeros((40, 30, 3), np.uint8)
    img[:5] = 255                      # white marker on the top rows, so a flip is visible
    return img


async def test_upright_page_costs_one_call():
    provider = ScriptedProvider(False)
    raw, name, final = await extract_oriented(marked_page(), provider, None)
    assert provider.calls == 1 and name == "scripted" and not raw.text_upside_down
    assert final[0, 0, 0] == 255       # untouched


async def test_upside_down_page_is_flipped_and_asked_again():
    provider = ScriptedProvider(True, False)
    raw, _, final = await extract_oriented(marked_page(), provider, None)
    assert provider.calls == 2 and not raw.text_upside_down
    assert final[-1, 0, 0] == 255 and final[0, 0, 0] == 0   # marker is now at the bottom
    assert provider.seen[1][-1, 0, 0] == 255                # the second call really got the flipped page


async def test_if_both_orientations_look_upside_down_keep_the_original():
    provider = ScriptedProvider(True, True)
    raw, _, final = await extract_oriented(marked_page(), provider, None)
    assert provider.calls == 2 and raw.text_upside_down
    assert final[0, 0, 0] == 255       # the flag is unreliable for this page: nothing was flipped


async def test_the_turned_page_is_shown_before_the_second_call_finishes():
    shown = []
    provider = ScriptedProvider(True, False)
    await extract_oriented(marked_page(), provider, None, on_flip=lambda img: shown.append(img[-1, 0, 0]))
    assert shown == [255]              # the marker is at the bottom: the reviewer sees the page upright


async def test_when_the_flip_is_rejected_the_original_is_shown_again():
    shown = []
    await extract_oriented(marked_page(), ScriptedProvider(True, True), None, on_flip=lambda img: shown.append(img[0, 0, 0]))
    assert shown == [0, 255]           # first the flipped page, then the original back
