"""Demo set: 3 fund forms whose fund name is damaged, 1 Maccabi-style, 1 hospital. Fictional data."""
import json, os, random, sys
from PIL import Image, ImageDraw, ImageFilter
import gen
from gen import W, H, ARIAL, ARIALB, COUR, heb, hand, highlight, barcode, received_stamp, scan_effects, rdate, rbirth, mobile, phone

random.seed(int(sys.argv[2]) if len(sys.argv) > 2 else 5)
NAVY, ORANGE, MAC_BLUE = (20, 45, 110), (235, 120, 30), (0, 85, 170)
WATERMARK = "מסמך לדוגמה - אינו בר תוקף"


def watermark(img):
    layer = Image.new("L", (1500, 160), 0)
    d = ImageDraw.Draw(layer)
    d.text((40, 30), gen.get_display(WATERMARK), font=ARIALB(90), fill=40)
    layer = layer.rotate(35, expand=True)
    grey = Image.new("RGB", layer.size, (150, 150, 150))
    img.paste(grey, ((W - layer.width) // 2, (H - layer.height) // 2), layer)


def wordmark(img, damage, colour, name, sub):
    """Fund name top-right. damage: 'strike' | 'blot' | 'torn' | None."""
    d = ImageDraw.Draw(img)
    f = ARIALB(64)
    t = gen.get_display(name)
    x1 = W - 70
    x0 = x1 - d.textlength(t, font=f)
    d.ellipse([x1 - 6, 52, x1 + 24, 82], fill=ORANGE if colour == NAVY else colour)
    d.text((x0, 40), t, font=f, fill=colour)
    heb(d, (x1, 118), sub, ARIAL(26), colour)
    # glyph boxes, to aim damage at a single letter (2nd letter from the right)
    xs, x = [], x0
    for ch in t:
        w = d.textlength(ch, font=f)
        xs.append((x, x + w)); x += w
    lx0, lx1 = xs[-2]
    if damage == "strike":
        ink = gen.INKS[1]
        for k in range(7):
            d.line([(lx0 - 4, 60 + k * 7), (lx1 + 4, 52 + k * 8)], fill=ink, width=4)
        d.line([(lx0 - 8, 95), (lx1 + 10, 50)], fill=ink, width=5)
    elif damage == "blot":
        blot = Image.new("L", (W, H), 0)
        bd = ImageDraw.Draw(blot)
        for _ in range(14):
            cx, cy = random.uniform(lx0, lx1), random.uniform(55, 100)
            r = random.uniform(12, 26)
            bd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
        blot = blot.filter(ImageFilter.GaussianBlur(3)).point(lambda v: 255 if v > 90 else 0)
        img.paste(Image.new("RGB", (W, H), (70, 55, 40)), (0, 0), blot)
    elif damage == "torn":
        # white-out tape across the first letters, as if covered by a sticker
        d.polygon([(xs[-3][0] - 6, 30), (W - 30, 22), (W - 25, 120), (xs[-3][0] + 4, 112)], fill=(252, 252, 248))
        d.line([(xs[-3][0] - 6, 30), (xs[-3][0] + 4, 112)], fill=(200, 200, 200), width=2)
        heb(d, (x1, 118), sub, ARIAL(26), colour)


def field_table(img, y, rows, label_w=330):
    """Very clear label | value table."""
    d = ImageDraw.Draw(img)
    rh = 58
    x0, x1 = 80, W - 80
    d.rectangle([x0, y, x1, y + rh * len(rows)], outline=(0, 0, 0), width=3)
    for i, (label, value) in enumerate(rows):
        yy = y + i * rh
        if i:
            d.line([(x0, yy), (x1, yy)], fill=(0, 0, 0), width=1)
        d.rectangle([x1 - label_w, yy + 1, x1 - 1, yy + rh - 1], fill=(232, 236, 244))
        heb(d, (x1 - 18, yy + 13), label, ARIALB(30))
        if any("֐" <= c <= "׿" for c in value):
            heb(d, (x1 - label_w - 22, yy + 12), value, ARIAL(32))
        else:
            vw = d.textlength(value, font=ARIALB(32))
            d.text((x1 - label_w - 22 - vw, yy + 11), value, font=ARIALB(32), fill=(0, 0, 0))
    d.line([(x1 - label_w, y), (x1 - label_w, y + rh * len(rows))], fill=(0, 0, 0), width=2)
    return y + rh * len(rows)


def central_sticker(img, xy, central):
    barcode(img, xy, w=210, h=60, label=central)
    d = ImageDraw.Draw(img)
    d.text((xy[0] + 220, xy[1] + 20), "GL.Cl", font=ARIALB(18), fill=(0, 0, 0))


def make_record(fund_label, kind):
    fn, ln = random.choice(gen.PATIENTS)
    test, code = random.choice(gen.TESTS)
    return {"fund": fund_label, "kind": kind, "first_name": fn, "last_name": ln, "id": gen.rid(),
            "birth": rbirth(), "commitment_no": str(random.randint(700000000, 799999999)),
            "central_no": str(random.randint(930000, 949999)), "test": test, "service_code": code,
            "sample": random.choice(gen.SAMPLES), "service_date": rdate(), "valid_until": rdate(2027),
            "provider": "המעבדה האזורית לנגיפים", "phone": mobile()}


def tpl_fund_form(r, brand, damage):
    img = Image.new("RGB", (W, H), "white")
    if brand == "meuhedet":
        wordmark(img, damage, NAVY, "מאוחדת", "קופת חולים")
    else:
        wordmark(img, None, MAC_BLUE, "מכבי", "שירותי בריאות")
    d = ImageDraw.Draw(img)
    central_sticker(img, (80, 50), r["central_no"])
    d = ImageDraw.Draw(img)
    heb(d, (W - 80, 175), f"תאריך הפקה: {rdate()}", ARIAL(26))
    d.rectangle([80, 175, 210, 225], outline=(0, 0, 0), width=3)
    heb(d, (192, 183), "מקור", ARIALB(30))
    title = "התחייבות לתשלום עבור שירותי בריאות"
    tw = d.textlength(gen.get_display(title), font=ARIALB(46))
    heb(d, ((W + tw) / 2, 250), title, ARIALB(46))
    y = field_table(img, 340, [
        ("מספר התחייבות", r["commitment_no"]),
        ("מספר מרכזי", r["central_no"]),
        ("שם פרטי", r["first_name"]),
        ("שם משפחה", r["last_name"]),
        ("תעודת זהות", r["id"]),
        ("תאריך לידה", r["birth"]),
        ("טלפון", r["phone"]),
    ])
    highlight(img, (W - 80 - 330 - 260, 345, W - 80 - 330 - 10, 393))
    d = ImageDraw.Draw(img)
    heb(d, (W - 80, y + 30), "פרטי השירות", ARIALB(32))
    y = field_table(img, y + 80, [
        ("נותן השירות", r["provider"]),
        ("שם השירות", r["test"]),
        ("קוד שירות", r["service_code"]),
        ("כמות", "1"),
        ("סוג דגימה", r["sample"]),
        ("תאריך הטיפול", r["service_date"]),
        ("תוקף ההתחייבות עד", r["valid_until"]),
    ])
    d = ImageDraw.Draw(img)
    for i, s in enumerate(["התחייבות בטופס זה היא רק עבור השירותים המופיעים לעיל, ורק למוסד הרפואי הנ\"ל.",
                           "יש להציג טופס זה בעת קבלת השירות."]):
        heb(d, (W - 80, y + 30 + i * 38), s, ARIAL(24))
    received_stamp(img, (330, y + 210))
    hand(img, (760, y + 160), r["sample"], size=72)
    footer_y = H - 70
    heb(d, (W - 80, footer_y - 40), "מפיק/ה: " + random.choice(gen.DOCTORS), ARIAL(22))
    gen.footer(ImageDraw.Draw(img))
    watermark(img)
    return img


def tpl_hospital(r):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    col = (110, 20, 60)
    gen.logo(d, (W - 70, 45), r["fund"], "המעבדה לחקר נגיפים", col)
    d.line([(80, 140), (W - 80, 140)], fill=col, width=3)
    central_sticker(img, (80, 40), r["central_no"])
    d = ImageDraw.Draw(img)
    heb(d, (W - 80, 165), f"תאריך: {rdate()}", ARIAL(26))
    heb(d, (W - 80, 215), "לכבוד: המעבדה האזורית לנגיפים", ARIAL(26))
    heb(d, (W - 80, 270), "הנדון: בקשה לביצוע בדיקה במעבדה חיצונית - התחייבות כספית", ARIALB(32))
    y = field_table(img, 340, [
        ("מספר התחייבות", r["commitment_no"]),
        ("מספר מרכזי", r["central_no"]),
        ("שם פרטי", r["first_name"]),
        ("שם משפחה", r["last_name"]),
        ("תעודת זהות", r["id"]),
        ("תאריך לידה", r["birth"]),
        ("מחלקה שולחת", random.choice(gen.DEPTS)),
    ])
    highlight(img, (W - 80 - 330 - 260, 345, W - 80 - 330 - 10, 393))
    d = ImageDraw.Draw(img)
    heb(d, (W - 80, y + 30), "פרטי הבדיקה", ARIALB(32))
    y = field_table(img, y + 80, [
        ("הבדיקה הנדרשת", r["test"]),
        ("מק\"ט / קוד שירות", r["service_code"]),
        ("סוג דגימה", r["sample"]),
        ("תאריך לקיחה", r["service_date"]),
        ("כמות לחיוב", "1"),
    ])
    d = ImageDraw.Draw(img)
    heb(d, (W - 80, y + 30), "מספר הדרישה מהווה מספר התחייבות. בדיקות שלא הוזמנו בטופס זה לא ישולמו.", ARIALB(24))
    heb(d, (W - 80, y + 120), "בברכה,", ARIAL(24))
    heb(d, (W - 80, y + 160), random.choice(gen.DOCTORS) + ", מנהל/ת המעבדה", ARIALB(26))
    gen.scribble_signature(img, (W - 520, y + 150))
    received_stamp(img, (330, y + 170))
    gen.footer(ImageDraw.Draw(img))
    watermark(img)
    return img


if __name__ == "__main__":
    out = sys.argv[1]
    plan = [("מאוחדת", "meuhedet", "strike"), ("מאוחדת", "meuhedet", "blot"), ("מאוחדת", "meuhedet", "torn"),
            ("מכבי", "maccabi", None), ("המרכז הרפואי הדקל", "hospital", None)]
    pages, truth = [], []
    for i, (label, brand, damage) in enumerate(plan, 1):
        r = make_record(label, brand)
        img = tpl_hospital(r) if brand == "hospital" else tpl_fund_form(r, brand, damage)
        pages.append(scan_effects(img))
        truth.append({"page": i, "fund_name_damaged": damage, **r})
        pages[-1].resize((620, 877)).save(os.path.join(gen.HERE, f"demo{i}.png"))
    pages[0].save(out, save_all=True, append_images=pages[1:], resolution=150)
    with open(os.path.splitext(out)[0] + " - תשובות.json", "w", encoding="utf-8") as fh:
        json.dump(truth, fh, ensure_ascii=False, indent=2)
    print("ok")
