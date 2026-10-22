"""Realistic, scattered-layout demo set: 3 fund docs with damaged fund name, 1 Maccabi-style, 1 hospital. Fictional data."""
import json, os, random, sys
from PIL import Image, ImageDraw, ImageFilter
import gen
from gen import W, H, F, WF, get_display, hand, highlight, barcode, received_stamp, scan_effects, rdate, rbirth, mobile, phone

random.seed(int(sys.argv[2]) if len(sys.argv) > 2 else 3)
BLACK, GREY, LINK = (0, 0, 0), (120, 120, 120), (0, 40, 160)
NAVY, ORANGE, MAC_BLUE = (20, 45, 110), (235, 120, 30), (0, 85, 170)

ARIAL = lambda s: F(WF + "arial.ttf", s)
ARIALB = lambda s: F(WF + "arialbd.ttf", s)
TAHOMA = lambda s: F(WF + "tahoma.ttf", s)
TAHOMAB = lambda s: F(WF + "tahomabd.ttf", s)
DAVID = lambda s: F(WF + "david.ttf", s)
DAVIDB = lambda s: F(WF + "davidbd.ttf", s)
GISHA = lambda s: F(WF + "gisha.ttf", s)
GISHAB = lambda s: F(WF + "gishabd.ttf", s)
COUR = lambda s: F(WF + "cour.ttf", s)
FRANK = lambda s: F(WF + "frank.ttf", s)


def R(d, xr, y, s, f, fill=BLACK):
    """RTL text, right edge at xr. Returns (x_left, width)."""
    t = get_display(s)
    w = d.textlength(t, font=f)
    d.text((xr - w, y), t, font=f, fill=fill)
    return xr - w, w


def L(d, xl, y, s, f, fill=BLACK):
    t = get_display(s)
    d.text((xl, y), t, font=f, fill=fill)
    return xl, d.textlength(t, font=f)


def RH(img, d, xr, y, s, f, h, fill=BLACK):
    """RTL text with a yellow highlighter stroke over it."""
    x, w = R(d, xr, y, s, f, fill)
    highlight(img, (x - 6, y - 3, x + w + 6, y + h))
    return x, w


def damaged_word(img, xr, y, word, f, colour, mode, letter=1):
    """Draw a word and damage one letter (index counted from the right edge). mode: strike|blot|cover."""
    d = ImageDraw.Draw(img)
    t = get_display(word)
    w = d.textlength(t, font=f)
    x0 = xr - w
    d.text((x0, y), t, font=f, fill=colour)
    boxes, x = [], x0
    for ch in t:
        cw = d.textlength(ch, font=f)
        boxes.append((x, x + cw)); x += cw
    lx0, lx1 = boxes[-1 - letter]
    asc = f.size
    top, bot = y + asc * 0.15, y + asc * 1.05
    if mode == "strike":
        ink = (25, 25, 35)
        for k in range(8):
            yy = top + (bot - top) * k / 8
            d.line([(lx0 - 3, yy + 6), (lx1 + 3, yy - 2)], fill=ink, width=max(2, asc // 18))
        d.line([(lx0 - 6, bot), (lx1 + 8, top)], fill=ink, width=max(3, asc // 14))
    elif mode == "blot":
        blot = Image.new("L", img.size, 0)
        bd = ImageDraw.Draw(blot)
        for _ in range(16):
            cx, cy = random.uniform(lx0, lx1), random.uniform(top, bot)
            r = random.uniform(asc * 0.15, asc * 0.38)
            bd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
        blot = blot.filter(ImageFilter.GaussianBlur(3)).point(lambda v: 255 if v > 90 else 0)
        img.paste(Image.new("RGB", img.size, (60, 50, 40)), (0, 0), blot)
    elif mode == "cover":
        # white correction tape over the first letters
        c0 = boxes[-1 - letter][0]
        d.polygon([(c0 - 4, top - 14), (xr + 14, top - 18), (xr + 18, bot + 10), (c0 + 4, bot + 14)], fill=(252, 252, 246))
        d.line([(c0 - 4, top - 14), (c0 + 4, bot + 14)], fill=(205, 205, 205), width=2)
    return x0, w


def sticker(img, xy, central, vertical_label=True):
    barcode(img, xy, w=200, h=58, label=central)
    d = ImageDraw.Draw(img)
    lbl = Image.new("L", (70, 30), 0)
    ImageDraw.Draw(lbl).text((4, 2), "GL.Cl", font=ARIALB(20), fill=255)
    lbl = lbl.rotate(90, expand=True) if vertical_label else lbl
    img.paste(Image.new("RGB", lbl.size, BLACK), (xy[0] + 212, xy[1] + 4), lbl)


def faint_mark(img):
    """Light diagonal 'sample' mark so the page cannot pass as a real document."""
    layer = Image.new("L", (1400, 140), 0)
    ImageDraw.Draw(layer).text((30, 20), get_display("מסמך לדוגמה - אינו בר תוקף"), font=ARIALB(80), fill=28)
    layer = layer.rotate(35, expand=True)
    img.paste(Image.new("RGB", layer.size, (150, 150, 150)), ((W - layer.width) // 2, (H - layer.height) // 2), layer)


def finish(img):
    gen.footer(ImageDraw.Draw(img))
    faint_mark(img)
    return img


def record(fund, kind):
    fn, ln = random.choice(gen.PATIENTS)
    test, code = random.choice(gen.TESTS)
    return {"fund": fund, "kind": kind, "first_name": fn, "last_name": ln, "id": gen.rid(), "birth": rbirth(),
            "commitment_no": str(random.randint(300000000, 799999999)), "central_no": str(random.randint(930000, 949999)),
            "test": test, "service_code": code, "sample": random.choice(gen.SAMPLES), "service_date": rdate(),
            "valid_until": rdate(2027), "phone": mobile(), "city": random.choice(gen.CITIES),
            "street": f"{random.choice(gen.STREETS)} {random.randint(1, 120)}"}


def masked_id_scribble(img, xy, r, size=40):
    """The handwritten 'ID - name' note that appears on almost every original page."""
    hand(img, xy, f"{r['id']} - {r['first_name']} {r['last_name']}", size=size, ink=random.choice([(20, 60, 200), (30, 30, 160)]), font=gen.HAND_HE[0])


# ------------------------------------------------------------------ 1: fund commitment (damaged: strike)
def doc_fund_commitment(r):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.ellipse([W - 95, 58, W - 63, 90], fill=ORANGE)
    damaged_word(img, W - 100, 30, "מאוחדת", ARIALB(84), NAVY, "strike", letter=2)
    R(d, W - 100, 128, "קופת חולים", GISHAB(30), NAVY)
    L(d, 70, 40, f"מוקד: *{random.randint(2000, 9999)}", ARIAL(22))
    sticker(img, (300, 40), r["central_no"])
    d.rectangle([70, 160, 200, 210], outline=BLACK, width=3)
    R(d, 182, 167, "מקור", ARIALB(30))
    R(d, W - 330, 150, f"תאריך הפקה: {rdate()}", ARIAL(24))
    R(d, W - 330, 180, "- עותק למוסד -", ARIAL(20), GREY)
    R(d, W - 140, 235, "התחייבות לתשלום עבור שירותי בריאות", ARIALB(42))
    x, _ = R(d, W - 300, 300, "התחייבות מספר", ARIALB(30))
    RH(img, d, x - 20, 297, r["commitment_no"], ARIALB(34), 40)
    R(d, W - 70, 370, f"תאריך הטיפול: {r['service_date']}", ARIALB(26))
    d.rectangle([70, 410, W - 70, 620], outline=BLACK, width=2)
    R(d, W - 85, 418, "נותן השירות", ARIALB(26))
    d.line([(70, 455), (W - 70, 455)], fill=BLACK)
    for i, (k, v) in enumerate([("שם", "בי\"ח " + random.choice(gen.HOSPITALS).split()[-1] + " - המעבדה האזורית לנגיפים"),
                                ("מחלקה/מרפאה", "מעבדה וירולוגית"), ("כתובת", f"{random.choice(gen.STREETS)} {random.randint(1, 50)} {random.choice(gen.CITIES)}"),
                                ("טלפון", phone())]):
        R(d, W - 85, 468 + i * 37, k, ARIALB(23))
        R(d, W - 300, 468 + i * 37, ": " + v, COUR(23))
    y0 = 660
    d.rectangle([70, y0, W - 70, y0 + 92], outline=BLACK, width=2)
    d.line([(70, y0 + 42), (W - 70, y0 + 42)], fill=BLACK)
    for xx in (190, 400):
        d.line([(xx, y0), (xx, y0 + 92)], fill=BLACK)
    R(d, 180, y0 + 8, "כמות", ARIALB(23)); R(d, 390, y0 + 8, "קוד השירות", ARIALB(23)); R(d, W - 85, y0 + 8, "שם השירות", ARIALB(23))
    d.text((120, y0 + 52), "1", font=COUR(26), fill=BLACK)
    d.text((255, y0 + 52), r["service_code"], font=COUR(26), fill=BLACK)
    R(d, W - 85, y0 + 52, "בדיקת מעבדה - " + r["test"], COUR(22))
    hand(img, (430, y0 - 52), r["test"], size=46, hebrew=False)
    d = ImageDraw.Draw(img)
    R(d, W - 70, 785, "התחייבות בטופס זה היא רק עבור השירותים המופיעים למעלה, ורק למוסד רפואי זה.", ARIALB(23))
    for i, s in enumerate(["רוצה לקבל את השירות במקום אחר? אם עדיין לא מימשת את טופס ההתחייבות",
                           "ניתן להגיש בקשה לביטול ולהנפקת טופס התחייבות חדש למרכז רפואי אחר מתוך הרשימה המופיעה",
                           "באתר/אפליקציה/מרפאות הקופה ו/או בעמדי\"ש הבא/ים.", "",
                           "לתשומת ליבך, הקופה לא תממן טיפול כפול, כלומר לא תממן שירות שניתן ללקוח פעמיים",
                           "עבור אותה הפניה.", "", "אם אינו שינוי בבחירתך, טופס זה הוא הטופס הנדרש לקבלת השירות."]):
        R(d, W - 70, 830 + i * 33, s, ARIAL(21))
    received_stamp(img, (300, 1170))
    y = 1330
    d.line([(70, y - 12), (W - 70, y - 12)], fill=BLACK, width=2)
    R(d, W - 70, y, "פרטי המבוטח/ת", ARIALB(26))
    R(d, W - 70, y + 42, "ת\"ז:", ARIALB(24)); RH(img, d, W - 150, y + 42, r["id"], ARIAL(25), 30)
    R(d, W - 70, y + 80, "שם פרטי:", ARIALB(24)); R(d, W - 200, y + 80, r["first_name"], ARIAL(25))
    R(d, W - 420, y + 80, "שם משפחה:", ARIALB(24)); R(d, W - 570, y + 80, r["last_name"], ARIAL(25))
    R(d, W - 70, y + 118, f"כתובת: {r['street']} {r['city']}", ARIAL(23))
    R(d, 520, y + 42, f"תאריך לידה: {r['birth']}", ARIAL(23))
    R(d, 520, y + 80, f"טלפונים: {r['phone']}", ARIAL(23))
    masked_id_scribble(img, (560, y - 40), r, size=36)
    d = ImageDraw.Draw(img)
    d.line([(70, y + 165), (W - 70, y + 165)], fill=BLACK)
    R(d, W - 70, y + 178, f"תוקף התחייבות זו עד תאריך {r['valid_until']}", ARIALB(24))
    R(d, 620, y + 178, "וכל עוד המבוטח/ת חבר/ה בקופה", ARIAL(21))
    R(d, W - 70, y + 215, f"מפיק/ת ההתחייבות: {random.choice(gen.DOCTORS)}", ARIAL(21))
    R(d, W - 70, y + 290, "יש להגיע עם כרטיס מגנטי ותעודה מזהה לקבלת השירות", ARIALB(25))
    return finish(img)


# ------------------------------------------------------------------ 2: hospital system print-screen (damaged: blot)
def doc_hospital_screen(r):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 120, H], fill=(200, 200, 200))  # printed screenshot margin
    d.line([(150, 12), (W - 40, 12)], fill=GREY, width=2)
    R(d, W - 60, 45, "מין", TAHOMAB(24)); R(d, W - 60, 72, "מקרה", TAHOMAB(24))
    R(d, 1000, 52, "זכר" if random.random() < .5 else "נקבה", TAHOMA(22))
    d.text((860, 76), str(random.randint(30000000, 39999999)), font=TAHOMA(22), fill=BLACK)
    R(d, 590, 42, "ביק.ראש.", TAHOMAB(22)); R(d, 590, 68, "Vst אחר.", TAHOMAB(22))
    d.text((330, 42), rdate(), font=TAHOMA(22), fill=BLACK); d.text((330, 68), r["service_date"], font=TAHOMA(22), fill=BLACK)
    R(d, W - 200, 104, f"שם פרטי: {r['first_name']}     שם משפחה: {r['last_name']}     ת.ז.: {r['id']}", TAHOMAB(23))
    masked_id_scribble(img, (620, -14), r, size=34)
    d = ImageDraw.Draw(img)
    d.line([(150, 140), (W - 40, 140)], fill=GREY)
    R(d, W - 60, 152, "נתוני ביקור", TAHOMA(23))
    d.rectangle([270, 180, W - 120, 600], outline=(190, 190, 190))
    labels = ["סוג מקרה", "סוג ביקור", "תאריך", "קטגוריית טיפול", "משך שהות מוערך", "סוג מבקר", "הערה", "גורם מפנה"]
    for i, k in enumerate(labels):
        R(d, W - 60, 195 + i * 44, k, TAHOMA(22), LINK if k == "הערה" else BLACK)

    def box(x0, y, w, s, f=TAHOMA(21)):
        d.rectangle([x0, y - 3, x0 + w, y + 30], outline=(160, 160, 160))
        R(d, x0 + w - 6, y, s, f)
    box(800, 195, 230, "חולה אמבולטורי  ▾")
    box(800, 239, 230, "01  ביקור במרפאה")
    box(820, 283, 210, r["service_date"])
    highlight(img, (830, 280, 1025, 316))
    box(960, 459, 70, "1"); R(d, 940, 459, "אזרח", TAHOMA(21))
    d.rectangle([560, 504, 1030, 534], outline=(160, 160, 160))
    box(980, 547, 50, "12")
    damaged_word(img, 965, 547, "מאוחדת", TAHOMA(22), BLACK, "blot", letter=1)
    highlight(img, (860, 544, 972, 578))
    d = ImageDraw.Draw(img)
    R(d, 770, 195, "תחום", TAHOMA(22), LINK); box(600, 195, 110, "אמבולטו")
    R(d, 770, 239, "סיבת ביקור", TAHOMA(22)); R(d, 770, 283, "שעה", TAHOMA(22))
    box(580, 283, 130, f"{random.randint(7, 17):02d}:{random.randint(0, 59):02d}:{random.randint(0, 59):02d}")
    R(d, 560, 195, "שער אמבולטור", TAHOMA(22)); R(d, 390, 195, "מקרה חירום", TAHOMA(22)); d.rectangle([398, 198, 418, 218], outline=GREY)
    R(d, 540, 283, "סטאטוס", TAHOMA(22)); box(290, 283, 140, "בפועל  ▾")
    R(d, 780, 547, "בי\"ח מפנה", TAHOMA(22), LINK)
    d.rectangle([600, 503, 640, 535], outline=GREY)
    R(d, W - 60, 630, "שיוך ארגוני", TAHOMA(22))
    R(d, W - 60, 675, "מח.סיעודית", TAHOMA(22), LINK); R(d, W - 60, 715, "חדר טיפולים", TAHOMA(22), LINK)
    box(930, 675, 100, random.choice(["השתמ", "פנימ", "ילדי"]))
    R(d, 860, 675, "השתלות מח", TAHOMA(21)); R(d, 690, 675, "מח.רפואית", TAHOMA(22), LINK)
    box(450, 675, 110, f"{random.randint(1100, 1199)}-רמ"); R(d, 430, 675, "מר.השתלות", TAHOMA(21))
    R(d, 690, 715, "מיטה", TAHOMA(22), LINK)
    d.rectangle([440, 712, 480, 748], outline=GREY)
    # handwritten central number + date, highlighted like the originals
    hand(img, (160, 380), r["central_no"], size=54, hebrew=False, angle=6)
    hand(img, (175, 450), r["service_date"][:5].replace(".", "/") + "/" + r["service_date"][-2:], size=48, hebrew=False, angle=5)
    highlight(img, (160, 395, 330, 450)); highlight(img, (170, 460, 330, 512))
    d = ImageDraw.Draw(img)
    y = 820
    d.line([(150, y), (W - 40, y)], fill=GREY)
    R(d, W - 60, y + 10, "קשרי ביטוח - סקירה", TAHOMA(23))
    tb = y + 50
    d.rectangle([150, tb, W - 40, tb + 36], fill=(236, 236, 236), outline=GREY)
    for i in range(14):
        d.rectangle([W - 60 - i * 46 - 34, tb + 4, W - 60 - i * 46, tb + 32], outline=(110, 110, 110))
    R(d, 470, tb + 6, "הזנה", TAHOMA(20)); d.text((180, tb + 6), "1   של   1", font=TAHOMA(20), fill=BLACK)
    hy = tb + 50
    for xr, s in [(W - 60, "מבוטח"), (W - 170, "שם מבוטח"), (800, "מבוטח מתא."), (680, "מבוטח עד"), (570, "מספר התחייבות"), (300, "סוג כיסוי")]:
        R(d, xr, hy, s, TAHOMA(20))
    highlight(img, (425, hy - 3, 575, hy + 28))
    d = ImageDraw.Draw(img)
    ry = hy + 40
    d.text((W - 60 - d.textlength("110021", font=TAHOMA(20)), ry), str(random.randint(110000, 119999)), font=TAHOMA(20), fill=LINK)
    x, _ = R(d, W - 170, ry, f"- {r['city']} מחוז", TAHOMA(20))
    damaged_word(img, x - 8, ry, "מאוחדת", TAHOMA(20), BLACK, "blot", letter=2)
    d = ImageDraw.Draw(img)
    d.text((695, ry), rdate(), font=TAHOMA(20), fill=BLACK)
    d.text((578, ry), r["valid_until"], font=TAHOMA(20), fill=BLACK)
    cno = "000" + r["commitment_no"]
    d.text((432 - 10, ry), cno, font=TAHOMA(20), fill=BLACK)
    highlight(img, (417, ry - 3, 427 + d.textlength(cno, font=TAHOMA(20)), ry + 28))
    d = ImageDraw.Draw(img)
    for i in range(3):
        d.rectangle([300, ry + i * 34, 322, ry + 22 + i * 34], outline=GREY)
    d.line([(250, 600), (250, 1200)], fill=(170, 170, 170))
    return finish(img)


# ------------------------------------------------------------------ 3: outsourced lab results (damaged: cover)
def doc_lab_results(r):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([70, 40, W - 70, 220], outline=GREY, width=2)
    d.line([(420, 40), (420, 220)], fill=GREY, width=2); d.line([(W - 420, 40), (W - 420, 220)], fill=GREY, width=2)
    d.polygon([(150, 170), (210, 80), (250, 130), (280, 95), (340, 170)], outline=(90, 90, 90), width=4)
    R(d, 310, 180, "מעבדה מרכזית", DAVID(26), GREY)
    R(d, 720, 100, "המעבדה המרכזית", DAVIDB(28))
    d.ellipse([W - 400, 95, W - 360, 135], outline=NAVY, width=5)
    damaged_word(img, W - 100, 80, "מאוחדת", ARIALB(64), NAVY, "cover", letter=2)
    highlight(img, (W - 410, 82, W - 90, 158))
    d = ImageDraw.Draw(img)
    title_no = str(random.randint(480000000, 489999999))
    R(d, W - 300, 240, f"דוח תוצאות מיקור חוץ לבדיקות מעבדה מס' {title_no}", DAVIDB(28))
    d.line([(300, 275), (W - 300, 275)], fill=BLACK)
    R(d, 740, 290, "תוצאות חלקיות", DAVIDB(26))
    y = 345
    R(d, W - 70, y, "שם משפחה:", DAVIDB(28)); RH(img, d, W - 225, y, r["last_name"], DAVID(30), 34)
    R(d, 760, y, "שם פרטי:", DAVIDB(28)); RH(img, d, 640, y, r["first_name"], DAVID(30), 34)
    R(d, 400, y, "ת.ז.:", DAVIDB(28)); RH(img, d, 330, y, r["id"], DAVID(30), 34)
    d.line([(70, y + 45), (W - 70, y + 45)], fill=BLACK, width=2)
    rows = [[("מין:", random.choice(["זכר", "נקבה"])), ("שם האב:", random.choice(["משה", "עלי", "יעקב", "סרגיי"])), ("תאריך לידה:", r["birth"]), ("גיל:", str(2026 - int(r["birth"][-4:])))],
            [("כתובת:", f"{r['street']} {r['city']}"), ("טלפון:", r["phone"]), ("", ""), ("פקס:", "0")],
            [("", ""), ("מס קבלה:", ""), ("", ""), ("", "")],
            [("תאריך קליטה:", r["service_date"] + " 10:20"), ("גורם שולח:", f"{random.randint(700000, 709999)} {r['city']}"), ("רופא שולח:", random.choice(gen.DOCTORS)), ("", "")],
            [("כתובת גורם שולח:", f"{random.choice(gen.STREETS)} {random.randint(1, 30)}"), ("טלפון גורם שולח:", phone()), ("פקס גורם שולח:", phone()), ("", "")]]
    xs = [W - 70, 860, 560, 260]
    for ri, row in enumerate(rows):
        yy = y + 65 + ri * 38
        for xr, (k, v) in zip(xs, row):
            if k:
                x, _ = R(d, xr, yy, k, DAVIDB(22))
                R(d, x - 10, yy, v, DAVID(22))
    highlight(img, (W - 330, y + 175, W - 170, y + 208))
    y2 = y + 270
    R(d, W - 70, y2, f"מס' הדגימה: {title_no}", DAVID(22)); R(d, 620, y2, f"תאריך לקיחה: {r['service_date']} 10:18", DAVID(22))
    d.line([(70, y2 + 35), (W - 70, y2 + 35)], fill=BLACK)
    for xr, s in [(W - 70, "תאריך אישור"), (760, "תוצאה"), (300, "שם בדיקה")]:
        R(d, xr, y2 + 45, s, DAVIDB(22))
    R(d, 300, y2 + 85, "מעבדות חוץ", DAVIDB(22))
    d.text((90, y2 + 120), r["test"], font=ARIAL(22), fill=BLACK)
    R(d, W - 70, y2 + 120, "//", DAVID(22)); R(d, 760, y2 + 120, "נשלח לתל השומר", DAVID(22)); R(d, 560, y2 + 120, "00:00", DAVID(22))
    d.rectangle([70, y2 + 170, W - 70, y2 + 240], outline=BLACK)
    d.line([(70, y2 + 205), (W - 70, y2 + 205)], fill=BLACK)
    R(d, W - 80, y2 + 175, "פעולת הפצה: 0", DAVID(20)); R(d, 720, y2 + 175, "תאריך הפצה:", DAVID(20))
    R(d, 350, y2 + 175, f"תאריך הדפסה: {r['service_date']} 16:49", DAVID(20))
    R(d, W - 300, y2 + 210, "המסמך מכיל מידע חסוי על פי חוק הגנת הפרטיות וחוק זכויות החולה.", DAVID(20))
    d.line([(70, y2 + 290), (W - 70, y2 + 290)], fill=GREY, width=2)
    R(d, W - 80, y2 + 300, "כל הזכויות שמורות", DAVID(18), GREY); R(d, 700, y2 + 300, "הופק ע\"י: משתמש מעבדה    גירסה 5.5  LabSys", DAVID(18), GREY)
    # commitment box bottom-right
    bx0, by0 = 560, 1100
    d.rectangle([bx0, by0, W - 70, by0 + 230], outline=BLACK, width=3)
    d.ellipse([W - 345, by0 + 14, W - 320, by0 + 39], outline=NAVY, width=3)
    damaged_word(img, W - 90, by0 + 8, "מאוחדת", ARIALB(30), NAVY, "cover", letter=2)
    d = ImageDraw.Draw(img)
    R(d, W - 360, by0 + 14, "מעבדה מרכזית", DAVIDB(24))
    R(d, W - 90, by0 + 52, f"טל: {phone()}  פקס: {phone()}", DAVID(19))
    d.line([(bx0, by0 + 80), (W - 70, by0 + 80)], fill=BLACK)
    for i, s in enumerate(["מסמך זה משמש התחייבות לתשלום עבור", "הבדיקה המצוינת בגוף הטופס.",
                           "מס' התחייבות: " + r["commitment_no"], "תשובת הבדיקה תשלח ישירות לרופא המטפל."]):
        if "התחייבות:" in s:
            RH(img, d, W - 90, by0 + 92 + i * 33, s, DAVIDB(24), 30)
        else:
            R(d, W - 90, by0 + 92 + i * 33, s, DAVIDB(22))
    gen.hand(img, (200, 1270), r["sample"], size=96, ink=(110, 110, 110), font=gen.HAND_HE[1])
    sticker(img, (600, 1400), r["central_no"])
    highlight(img, (600, 1460, 800, 1495))
    received_stamp(img, (320, 1560))
    return finish(img)


# ------------------------------------------------------------------ 4: Maccabi-style dense form 17
def doc_dense_form17(r):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    f, fb = GISHA(20), GISHAB(20)
    x, _ = R(d, 860, 30, "מכבי", GISHAB(90), MAC_BLUE)
    d.ellipse([862, 60, 900, 98], fill=MAC_BLUE)
    R(d, 860, 135, "שירותי בריאות", GISHA(26), MAC_BLUE)
    highlight(img, (x - 10, 40, 910, 135))
    d = ImageDraw.Draw(img)
    R(d, 220, 40, "-העתק-", GISHAB(30)); R(d, 280, 85, f"תאריך: {rdate()}", f)
    sticker(img, (80, 150), r["central_no"])
    highlight(img, (80, 210, 280, 245))
    d = ImageDraw.Draw(img)
    y = 190
    R(d, W - 60, y, "חסוי/אישי", GISHAB(26))
    district = random.choice(["מרכז", "שרון", "דרום", "ירושלים"])
    for i, s in enumerate([f"מחוז מטפל: 004 {district}   מחוז מנפק: 004 {district}",
                           f"מנהלת מטפל: 01 מנהלת {r['city']}   מרפאה מנפקת: {random.randint(3000, 3999)} מרפאת {random.choice(gen.STREETS)}   טלפון {phone()}",
                           f"מרפאה מטפל: {random.randint(3000, 3999)} מרפאת {random.choice(gen.STREETS)} המעוגר טלפון {phone()}"]):
        R(d, W - 60, y + 40 + i * 28, s, f)
    yt = y + 140
    R(d, W - 280, yt, "התחייבות לתשלום עבור שירותי בריאות) טופס 17(", GISHAB(32))
    x, _ = R(d, W - 330, yt + 42, "לטיפולים אמבולטוריים מספר:", GISHAB(32))
    RH(img, d, x - 6, yt + 40, r["commitment_no"], GISHAB(36), 42)
    R(d, W - 60, yt + 100, f"לכבוד: המעבדה האזורית לנגיפים  לקביעת תור {phone()}", f)
    R(d, W - 60, yt + 128, "מטופל:", fb)
    R(d, W - 140, yt + 128, f"שם פרטי: {r['first_name']}   שם משפחה: {r['last_name']}   ת.ז.: {r['id']}", f)
    masked_id_scribble(img, (W - 980, yt + 112), r, size=36)
    d = ImageDraw.Draw(img)
    R(d, W - 60, yt + 156, f"רופא מפנה: {random.randint(100000, 199999)} {random.choice(gen.DOCTORS)}", f)
    yt2 = yt + 200
    R(d, W - 60, yt2, "קוד", fb); R(d, W - 60, yt2 + 25, "שירות", fb)
    R(d, W - 300, yt2 + 25, "תאור הטיפול / בדיקה", fb); R(d, 280, yt2 + 25, "כמות", fb)
    R(d, 160, yt2, "קוד", fb); R(d, 160, yt2 + 25, "משה\"ב", fb)
    d.line([(100, yt2 + 55), (W - 400, yt2 + 55)], fill=BLACK)
    R(d, W - 60, yt2 + 65, str(random.randint(70000, 79999)), f)
    R(d, W - 180, yt2 + 65, f"בדיקה: {r['test']} - לרבות באמצעות זיהוי חומצת גרעין נגיפית", f)
    R(d, 265, yt2 + 65, "1", f); R(d, 160, yt2 + 65, r["service_code"], f)
    R(d, W - 60, yt2 + 100, f"תאריך התור: {r['service_date']}", f); R(d, W - 520, yt2 + 100, f"תאריך תוקף ההתחייבות עד: {r['valid_until']}", f)
    R(d, W - 60, yt2 + 128, "התחייבות בטופס זה היא רק עבור השירותים המופיעים למעלה ורק למוסד רפואי זה ובתנאי שהמטופל רשום בקופה במועד מתן השירות", GISHA(18))
    yb = yt2 + 175
    R(d, W - 60, yb, "חשוב: כל בתי החולים עומדים לרשותך!", GISHAB(34))
    R(d, W - 60, yb + 55, "רוצה לקבל את השירות במקום אחר? אם עדיין לא מימשת את ההתחייבות, אפשר לבטל ולהוציא בקלות טופס התחייבות", fb)
    R(d, W - 60, yb + 82, "חדש למוסד רפואי אחר מתוך רשימת הספקים בהסדר", fb)
    R(d, W - 60, yb + 125, "לספקים נוספים ניתן לפנות לצוות המרפאה או לנציגים הדיגיטליים", fb)
    R(d, W - 60, yb + 170, "ספקים בהסדר בחירה", fb); R(d, 760, yb + 170, "יישוב", fb); R(d, 320, yb + 170, "טלפון לזימון תור", fb)
    R(d, W - 60, yb + 198, "מרפאת קהילה", f); R(d, 320, yb + 198, f"*{random.randint(2000, 9999)}", f)
    R(d, W - 60, yb + 250, "מאחלים לך בריאות טובה!", GISHAB(32))
    bullets = ["אם אין שינוי בבחירתך, עמוד זה הוא הטופס הנדרש לקבלת השירות",
               "טופס התחייבות זמין לעיון ולהדפסה באזור האישי באתר ובאפליקציה",
               "להוצאת טופס התחייבות חדש למוסד רפואי אחר יש לפנות לאזור האישי באתר/באפליקציה או למרפאה",
               "לאיתור שירותים ונותני שירות ניתן להיכנס לספר השירות באתר הקופה",
               "באחריות בית החולים/המכון לצרף להזמנה לביקור מכתב המפרט את מצב המטופל ואת הבדיקות הנדרשות",
               "ההתחייבות לא תישא בכל עלות חלקית או מלאה של שירות רפואי אחר או שונה, לרבות שירות רפואי פרטי",
               "ההתחייבות תכובד בכפוף להוראות כל דין והסכם ובעבור שירותים שניתנו על פיו",
               "אפשר לקבל את השירות במוסד רפואי כל עוד המוסד מופיע ברשימה, ומציע את השירות שמתאים לך",
               "הקופה תכבד התחייבות זו פעם אחת עבור שירות אחד, לא ניתן להשתמש בהתחייבות אם נוצלה כבר",
               "במידה ונותן השירות בחר לתת שירותים נוספים, התחייבות זו תכובד בכפוף להסכם",
               "התשלום מותנה בשליחת מכתב/סיכום רפואי חתום ע\"י רופא בית החולים, אל רופא המשפחה של המטופל"]
    for i, s in enumerate(bullets):
        R(d, W - 60, yb + 300 + i * 30, "*" + s, GISHA(19))
    return finish(img)


# ------------------------------------------------------------------ 5: hospital outside-lab request
def doc_hospital_request(r):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    hosp = random.choice(gen.HOSPITALS)
    col = (40, 40, 40)
    # six-pointed star style emblem + name, like a hospital letterhead
    cx, cy = 140, 85
    for ang in (0, 180):
        pts = [(cx + 45 * __import__("math").cos(__import__("math").radians(a + ang + 90)), cy + 45 * __import__("math").sin(__import__("math").radians(a + ang + 90))) for a in (0, 120, 240)]
        d.polygon(pts, outline=col, width=4)
    RH(img, d, 600, 50, hosp, FRANK(34), 40)
    d.text((200, 100), "MEDICAL CENTER - VIROLOGY DEPT.", font=ARIALB(18), fill=col)
    R(d, W - 70, 40, "ירושלים" if random.random() < .5 else r["city"], FRANK(22))
    sticker(img, (W - 330, 80), r["central_no"])
    highlight(img, (W - 330, 140, W - 130, 175))
    d = ImageDraw.Draw(img)
    R(d, 820, 200, "בקשה לבדיקה במעבדה מחוץ למרכז הרפואי", FRANK(32))
    d.line([(330, 240), (820, 240)], fill=BLACK)
    R(d, W - 70, 270, "לכבוד:", FRANK(24)); R(d, W - 160, 270, "המעבדה האזורית לנגיפים", COUR(24))
    R(d, 520, 270, "מחלקה:", FRANK(24)); R(d, 420, 270, random.choice(gen.DEPTS), COUR(24))
    R(d, W - 70, 310, f"תאריך הבקשה: {r['service_date']}", FRANK(24)); R(d, 520, 310, f"מספר בקשה: {random.randint(250000, 259999)}", FRANK(24))
    R(d, W - 70, 370, "פרטי המטופל:", FRANK(28))
    d.line([(W - 260, 402), (W - 70, 402)], fill=BLACK)
    R(d, W - 70, 420, "שם פרטי:", FRANK(24)); R(d, W - 200, 420, r["first_name"], COUR(26))
    R(d, 760, 420, "שם משפחה:", FRANK(24)); R(d, 620, 420, r["last_name"], COUR(26))
    R(d, W - 70, 465, "מספר זהות:", FRANK(24)); RH(img, d, W - 220, 465, r["id"], COUR(26), 30)
    R(d, 760, 465, "תאריך לידה:", FRANK(24)); R(d, 610, 465, r["birth"], COUR(26))
    R(d, W - 70, 510, "מין:", FRANK(24)); R(d, W - 140, 510, random.choice(["זכר", "נקבה"]), COUR(24))
    R(d, 760, 510, "קופת חולים:", FRANK(24)); R(d, 600, 510, random.choice(["כללית", "לאומית"]), COUR(24))
    masked_id_scribble(img, (420, 340), r, size=36)
    d = ImageDraw.Draw(img)
    R(d, W - 70, 580, "אבחנה / מידע קליני:", FRANK(24))
    d.text((150, 580), random.choice(["FEVER OF UNKNOWN ORIGIN", "MENINGITIS / ENCEPHALITIS", "SUSPECTED CONGENITAL INFECTION"]), font=ARIAL(22), fill=BLACK)
    R(d, W - 70, 625, "הבדיקה המבוקשת:", FRANK(24))
    d.ellipse([150, 610, 640, 670], outline=(25, 25, 35), width=3)
    d.text((180, 625), r["test"], font=ARIALB(24), fill=BLACK)
    R(d, W - 70, 670, f"סוג הדגימה: {r['sample']}", FRANK(24)); R(d, 760, 670, f"קוד שירות: {r['service_code']}", FRANK(24))
    d.rectangle([150, 740, W - 70, 840], outline=BLACK, width=2)
    R(d, W - 90, 750, "1. בקשה זו אך ורק עבור הבדיקה המצוינת בטופס זה.", FRANK(22))
    R(d, W - 90, 785, "2. בקשה זו תהיה בתוקף רק עם חותמת המרכז הרפואי ומספר התחייבות.", FRANK(22))
    hand(img, (180, 860), r["sample"], size=90, ink=(25, 25, 35))
    d = ImageDraw.Draw(img)
    R(d, W - 70, 1000, "התחייבות עבור בדיקות חוץ", FRANK(28))
    d.line([(W - 360, 1035), (W - 70, 1035)], fill=BLACK)
    R(d, W - 70, 1060, "מספר התחייבות:", FRANK(26)); RH(img, d, W - 270, 1058, r["commitment_no"], COUR(30), 34)
    R(d, 650, 1060, "תאריך:", FRANK(26)); RH(img, d, 560, 1058, r["service_date"], COUR(28), 34)
    R(d, W - 70, 1105, "המרכז הרפואי מתחייב לשלם עבור הבדיקה המבוקשת בלבד.", FRANK(22))
    R(d, W - 70, 1200, "אישור ההנהלה", FRANK(26))
    d.line([(W - 240, 1232), (W - 70, 1232)], fill=BLACK)
    R(d, W - 70, 1250, f"שם המאשר/ת: {random.choice(gen.DOCTORS)}", FRANK(22)); R(d, 560, 1250, f"תאריך: {r['service_date']}", FRANK(22))
    gen.scribble_signature(img, (700, 1300))
    received_stamp(img, (340, 1400))
    d = ImageDraw.Draw(img)
    d.line([(70, 1600), (W - 70, 1600)], fill=GREY)
    d.text((80, 1615), f"{hosp.split()[-1].upper() if False else 'MEDICAL CENTER'}  |  TEL {phone()}  |  FAX {phone()}", font=ARIAL(18), fill=GREY)
    return finish(img)


if __name__ == "__main__":
    out = sys.argv[1]
    plan = [("מאוחדת", "strike", doc_fund_commitment), ("מאוחדת", "blot", doc_hospital_screen),
            ("מאוחדת", "cover", doc_lab_results), ("מכבי", None, doc_dense_form17), ("בית חולים", None, doc_hospital_request)]
    pages, truth = [], []
    for i, (fund, damage, fn) in enumerate(plan, 1):
        r = record(fund, fn.__name__)
        pages.append(scan_effects(fn(r)))
        truth.append({"page": i, "fund_name_damaged": damage, **r})
        pages[-1].resize((620, 877)).save(os.path.join(gen.HERE, f"real{i}.png"))
    pages[0].save(out, save_all=True, append_images=pages[1:], resolution=150)
    with open(os.path.splitext(out)[0] + " - תשובות.json", "w", encoding="utf-8") as fh:
        json.dump(truth, fh, ensure_ascii=False, indent=2)
    print("ok")
