"""Barcode decoding: every valid barcode on a page, with boxes in the coordinates of the page that was passed in."""
from types import SimpleNamespace

import numpy as np
import pytest
import zxingcpp

from app.pipeline import barcodes
from app.pipeline.barcodes import UPSCALE, decode_barcodes


def page_with(text: str, at=(60, 80), width_modules: int = 2) -> np.ndarray:
    """A white page with one Code128 barcode drawn on it."""
    bars = zxingcpp.write_barcode(zxingcpp.BarcodeFormat.Code128, text, width=0, height=0)
    code = np.asarray(bars)
    code = np.kron(code, np.ones((1, width_modules), np.uint8)) if width_modules > 1 else code
    page = np.full((900, 700), 255, np.uint8)
    h = 70
    strip = np.repeat(code[:1, :], h, axis=0)
    page[at[1]:at[1] + h, at[0]:at[0] + strip.shape[1]] = strip
    return page


def result(text: str, valid: bool = True, box=(10, 20, 40, 30)):
    x, y, w, h = box
    corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    pts = [SimpleNamespace(x=cx, y=cy) for cx, cy in corners]
    pos = SimpleNamespace(top_left=pts[0], top_right=pts[1], bottom_right=pts[2], bottom_left=pts[3])
    return SimpleNamespace(valid=valid, text=text, format=SimpleNamespace(name="Code128"), position=pos)


class TestDecoding:
    def test_reads_a_barcode_and_says_where_it_is(self):
        found = decode_barcodes(page_with("939376", at=(60, 80)))
        assert [b.text for b in found] == ["939376"]
        x, y, w, h = found[0].box
        assert 40 <= x <= 80 and 70 <= y <= 100 and w > 40       # near where it was drawn

    def test_reads_a_colour_image_too(self):
        gray = page_with("730578626")
        assert [b.text for b in decode_barcodes(np.dstack([gray] * 3))] == ["730578626"]

    def test_a_blank_page_has_none(self):
        assert decode_barcodes(np.full((900, 700), 255, np.uint8)) == []

    def test_several_barcodes_on_one_page_are_all_found(self):
        page = page_with("111111", at=(60, 80))
        second = page_with("222222", at=(60, 300))
        both = np.minimum(page, second)
        assert sorted(b.text for b in decode_barcodes(both)) == ["111111", "222222"]


class TestVariants:
    @pytest.fixture()
    def fake(self, monkeypatch):
        """Scripts what zxing returns for each of the three images decode_barcodes tries: plain, binarized, enlarged."""
        calls: list[tuple[int, int]] = []
        script: dict[int, list] = {}

        def read_barcodes(img, **kw):
            calls.append(img.shape)
            return script.get(len(calls), [])

        monkeypatch.setattr(barcodes.zxingcpp, "read_barcodes", read_barcodes)
        return SimpleNamespace(calls=calls, script=script)

    def test_tries_the_page_as_is_binarized_and_enlarged(self, fake):
        decode_barcodes(np.full((200, 100), 255, np.uint8))
        assert fake.calls == [(200, 100), (200, 100), (300, 150)]       # the third is 1.5x

    def test_a_barcode_found_only_on_the_enlarged_page_has_its_box_mapped_back(self, fake):
        fake.script[3] = [result("939376", box=(150, 300, 300, 60))]    # coordinates on the enlarged page
        (found,) = decode_barcodes(np.full((900, 700), 255, np.uint8))
        assert found.box == (round(150 / UPSCALE), round(300 / UPSCALE), round(300 / UPSCALE), round(60 / UPSCALE))

    def test_a_barcode_found_at_normal_size_keeps_its_box(self, fake):
        fake.script[1] = [result("939376", box=(150, 300, 300, 60))]
        assert decode_barcodes(np.full((900, 700), 255, np.uint8))[0].box == (150, 300, 300, 60)

    def test_the_same_text_found_by_several_variants_is_reported_once_from_the_first(self, fake):
        fake.script[1] = [result("939376", box=(10, 20, 40, 30))]
        fake.script[3] = [result("939376", box=(15, 30, 60, 45))]
        found = decode_barcodes(np.full((900, 700), 255, np.uint8))
        assert [b.text for b in found] == ["939376"] and found[0].box == (10, 20, 40, 30)

    def test_each_variant_can_add_what_the_others_missed(self, fake):
        fake.script[1] = [result("111111")]
        fake.script[2] = [result("222222")]
        fake.script[3] = [result("333333")]
        assert [b.text for b in decode_barcodes(np.full((900, 700), 255, np.uint8))] == ["111111", "222222", "333333"]

    def test_results_that_are_not_valid_or_have_no_text_are_ignored(self, fake):
        fake.script[1] = [result("999999", valid=False), result("", valid=True)]
        assert decode_barcodes(np.full((900, 700), 255, np.uint8)) == []
