"""Synthetic scanned 'commitment' documents with handwritten annotations (fictional data)."""
import random, math, sys, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
from bidi.algorithm import get_display

random.seed(int(sys.argv[2]) if len(sys.argv) > 2 else 7)
HERE = os.path.dirname(os.path.abspath(__file__))
FD = os.path.join(HERE, "fonts")
WF = "C:/Windows/Fonts/"
W, H = 1240, 1754  # A4 @150dpi

def F(name, size): return ImageFont.truetype(name, size)
ARIAL = lambda s: F(WF + "arial.ttf", s)
ARIALB = lambda s: F(WF + "arialbd.ttf", s)
DAVID = lambda s: F(WF + "david.ttf", s)
COUR = lambda s: F(WF + "cour.ttf", s)
HAND_HE = [os.path.join(FD, "GveretLevin-Regular.ttf"), os.path.join(FD, "Karantina-Regular.ttf"),
           os.path.join(FD, "AmaticSC-Bold.ttf")]
HAND_EN = [os.path.join(FD, "Caveat.ttf"), os.path.join(FD, "AmaticSC-Bold.ttf")]
INKS = [(20, 40, 150), (25, 25, 35), (30, 60, 170), (10, 10, 90)]
YELLOW = (250, 245, 90)

PATIENTS = [
    ("יוסף", "אברהם"), ("מרים", "כהן"), ("אחמד", "חאג' יחיא"), ("נטליה", "קוזלוב"), ("טספאיה", "מנגיסטו"),
    ("רחל", "בן דוד"), ("עומר", "סעדי"), ("שירה", "לוי"), ("איגור", "פטרוב"), ("פאטמה", "אבו ריא"),
    ("דוד", "מזרחי"), ("נועה", "פרידמן"), ("ח'אלד", "נסאר"), ("אסתר", "ביטון"), ("יעל", "אלמוג"),
    ("מוחמד", "עודה"), ("אולגה", "סמירנוב"), ("ברוך", "ויסמן"), ("סיוון", "טל"), ("אביטל", "גבאי"),
    ("ליאור", "שטרן"), ("סלמה", "חורי"), ("יצחק", "דהן"), ("מאיה", "רוזנברג"), ("אדיסו", "טקלה"),
    ("רינה", "אוחיון"), ("ג'ורג'", "חדאד"), ("תמר", "ליבוביץ"), ("אלכסנדר", "וולקוב"), ("הדס", "נחמיאס"),
]
FUNDS = ["קופת חולים שלום", "בריאות הגליל", "קופת חולים ארצית", "שירותי בריאות המרכז"]
HOSPITALS = ["המרכז הרפואי הדקל", "בית החולים עמק השרון", "המרכז הרפואי גבעת הזיתים", "בית החולים נווה ים"]
LABS = ["מעבדת אלון לבדיקות רפואיות", "מעבדת רימון בע\"מ", "מעבדות צפון רפואיות"]
CITIES = ["תל אביב", "חיפה", "באר שבע", "נצרת", "אשדוד", "רמלה", "ירושלים", "עפולה"]
STREETS = ["הרצל", "ויצמן", "הנביאים", "בן גוריון", "האלה", "הזית", "רוטשילד", "הגפן"]
TESTS = [("WEST NILE PCR", "87798"), ("CMV IgG+IgM", "86644"), ("HERPES 1,2 PCR", "87529"),
         ("MEASLES RT PCR", "87250"), ("ZIKA VIRUS IgM", "86790"), ("HBV DNA", "87517"),
         ("HCV RNA", "87522"), ("EBV PANEL", "86663"), ("CHIKUNGUNYA IgG+IgM", "86790"),
         ("DENGUE NS1", "87449"), ("RSV PCR", "87634"), ("ENTEROVIRUS PCR", "87498")]
SAMPLES = ["נסיוב", "דם מלא", "שתן", "ע\"ד", "CSF", "משטח לוע", "פלזמה"]
DEPTS = ["פנימית א'", "ילדים ב'", "נוירולוגיה", "מיון", "יולדות", "טיפול נמרץ", "אונקולוגיה"]
DOCTORS = ["ד\"ר רונית שגיא", "ד\"ר סאמי עזאם", "ד\"ר מיכאל גרין", "ד\"ר אנה ברקוביץ", "ד\"ר עידו פלד"]


def rid(): return "".join(str(random.randint(0, 9)) for _ in range(9))
def rdate(y=2026): return f"{random.randint(1,28):02d}.{random.randint(1,12):02d}.{y}"
def rbirth(): return f"{random.randint(1,28):02d}.{random.randint(1,12):02d}.{random.randint(1940,2022)}"
def phone(): return f"0{random.choice([2,3,4,8,9])}-{random.randint(5000000,9999999)}"
def mobile(): return f"05{random.randint(0,8)}-{random.randint(1000000,9999999)}"


def heb(d, xy_right, text, font, fill=(0, 0, 0)):
    """Draw RTL text with its right edge at xy_right[0]."""
    t = get_display(text)
    w = d.textlength(t, font=font)
    d.text((xy_right[0] - w, xy_right[1]), t, font=font, fill=fill)
    return w


def ltr(d, xy, text, font, fill=(0, 0, 0)):
    d.text(xy, text, font=font, fill=fill)
    return d.textlength(text, font=font)


def highlight(img, box):
    x0, y0, x1, y1 = box
    hl = Image.new("RGB", img.size, (255, 255, 255))
    hd = ImageDraw.Draw(hl)
    hd.polygon([(x0 + random.randint(-4, 4), y0 + random.randint(-3, 3)), (x1 + random.randint(-4, 6), y0 + random.randint(-3, 3)),
                (x1 + random.randint(-4, 6), y1 + random.randint(-3, 3)), (x0 + random.randint(-4, 4), y1 + random.randint(-3, 3))], fill=YELLOW)
    img.paste(ImageChops.multiply(img, hl))


def hand(img, xy, text, size=None, hebrew=None, ink=None, angle=None, font=None, anchor_right=False):
    """Paste handwriting: rendered on a layer, wobbled and rotated."""
    if hebrew is None:
        hebrew = any("\u0590" <= c <= "\u05ff" for c in text)
    size = size or random.randint(38, 56)
    fpath = font or random.choice(HAND_HE if hebrew else HAND_EN)
    f = F(fpath, size)
    t = get_display(text) if hebrew else text
    ink = ink or random.choice(INKS)
    tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
    tw = int(tmp.textlength(t, font=f)) + 40
    th = int(size * 1.8)
    layer = Image.new("L", (tw, th), 0)
    ld = ImageDraw.Draw(layer)
    # per-glyph jitter for a less mechanical look
    x = 20
    for ch in t:
        ld.text((x, size * 0.3 + random.uniform(-2.5, 2.5)), ch, font=f, fill=255)
        x += tmp.textlength(ch, font=f) * random.uniform(0.95, 1.06)
    # slight wave distortion
    amp, per = random.uniform(1, 3), random.uniform(80, 200)
    waved = Image.new("L", layer.size, 0)
    for cx in range(0, layer.width, 2):
        dy = int(amp * math.sin(cx / per * 2 * math.pi))
        waved.paste(layer.crop((cx, 0, cx + 2, th)), (cx, dy))
    if random.random() < 0.5:
        waved = waved.filter(ImageFilter.MaxFilter(3))  # thicker pen
    waved = waved.rotate(angle if angle is not None else random.uniform(-7, 7), expand=True, resample=Image.BICUBIC)
    colour = Image.new("RGB", waved.size, ink)
    x0, y0 = xy
    if anchor_right:
        x0 -= waved.width
    img.paste(colour, (int(x0), int(y0)), waved)


def scribble_signature(img, xy, w=160, ink=None):
    ink = ink or random.choice(INKS)
    d = ImageDraw.Draw(img)
    x, y = xy
    pts = []
    for i in range(random.randint(20, 35)):
        pts.append((x + i * w / 30 + random.uniform(-6, 6), y + random.uniform(-18, 18) * math.sin(i * random.uniform(0.6, 1.4))))
    d.line(pts, fill=ink, width=3, joint="curve")
    d.line([(x - 5, y + 22), (x + w * 0.8, y + 16 + random.uniform(-6, 6))], fill=ink, width=2)


def barcode(img, xy, w=230, h=70, label=None, sticker=True):
    d = ImageDraw.Draw(img)
    x, y = xy
    if sticker:
        d.rectangle([x - 8, y - 8, x + w + 8, y + h + 40], fill=(255, 255, 255), outline=(200, 200, 200))
    cx = x
    while cx < x + w:
        bw = random.choice([2, 2, 3, 4, 5])
        if random.random() < 0.55:
            d.rectangle([cx, y, cx + bw - 1, y + h], fill=(0, 0, 0))
        cx += bw
    label = label or str(random.randint(930000, 949999))
    d.text((x + w / 2 - d.textlength(label, font=ARIALB(26)) / 2, y + h + 4), label, font=ARIALB(26), fill=(0, 0, 0))
    return label


def stamp(img, center, lines, colour=(40, 60, 120), angle=None):
    sw, sh = 340, 190
    layer = Image.new("L", (sw, sh), 0)
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([6, 6, sw - 6, sh - 6], radius=18, outline=255, width=5)
    y = 18
    for i, (txt, sz) in enumerate(lines):
        f = DAVID(sz) if i != 1 else ARIALB(sz)
        t = get_display(txt)
        d.text(((sw - d.textlength(t, font=f)) / 2, y), t, font=f, fill=255)
        y += sz + 12
    # ink unevenness
    noise = Image.effect_noise((sw, sh), 90).point(lambda v: 255 if v > 95 else 0)
    layer = ImageChops.multiply(layer, noise.convert("L"))
    layer = layer.filter(ImageFilter.GaussianBlur(0.7))
    layer = layer.rotate(angle if angle is not None else random.uniform(-14, 14), expand=True, resample=Image.BICUBIC)
    col = Image.new("RGB", layer.size, colour)
    img.paste(col, (int(center[0] - layer.width / 2), int(center[1] - layer.height / 2)), layer)


def received_stamp(img, center):
    dt = f"{random.randint(1,28):02d} -{random.randint(1,12):02d}- 2026"
    stamp(img, center, [("התקבל", 54), (dt, 30), ("המעבדה האזורית לנגיפים", 24), ("המרכז הרפואי המשולב", 22)])
    return dt


def scan_effects(img, rotate_page=False):
    if rotate_page:
        img = img.rotate(90, expand=True).resize((W, H))
    img = img.rotate(random.uniform(-1.2, 1.2), expand=False, fillcolor=(255, 255, 255), resample=Image.BICUBIC)
    g = Image.effect_noise(img.size, 18).convert("RGB")
    img = ImageChops.multiply(img, Image.eval(g, lambda v: 235 + v // 12 if v < 240 else 255))
    img = img.filter(ImageFilter.GaussianBlur(0.45))
    d = ImageDraw.Draw(img)
    # dark scanner edge + stray specks
    if random.random() < 0.6:
        d.rectangle([0, 0, W, random.randint(3, 10)], fill=(90, 90, 90))
    for _ in range(random.randint(10, 40)):
        x, y = random.randint(0, W), random.randint(0, H)
        r = random.randint(1, 2)
        d.ellipse([x, y, x + r, y + r], fill=(80, 80, 80))
    return img


def logo(d, xy_right, name, sub=None, colour=(0, 90, 160)):
    x, y = xy_right
    d.ellipse([x - 70, y, x - 10, y + 60], outline=colour, width=6)
    d.line([(x - 55, y + 30), (x - 25, y + 30)], fill=colour, width=6)
    d.line([(x - 40, y + 15), (x - 40, y + 45)], fill=colour, width=6)
    heb(d, (x - 85, y + 2), name, ARIALB(40), colour)
    if sub:
        heb(d, (x - 85, y + 50), sub, ARIAL(22), colour)


def footer(d):
    t = "מסמך סינתטי לצורכי פיתוח ובדיקות - נתונים פיקטיביים"
    heb(d, (W - 60, H - 40), t, ARIAL(14), (150, 150, 150))


def common_annotations(img, p, sample_xy=None, stamp_xy=None, sticker_xy=None):
    """The things that appear on almost every page: barcode sticker, handwritten ID/name, sample, stamp."""
    sx, sy = sticker_xy or (random.choice([60, 820]), random.choice([60, 180]))
    barcode(img, (sx, sy), w=200, h=60)
    ImageDraw.Draw(img).text((sx + 210, sy + 20), "GL.Cl", font=ARIALB(18), fill=(0, 0, 0))
    if sample_xy:
        hand(img, sample_xy, random.choice(SAMPLES), size=random.randint(60, 80))
    if stamp_xy and random.random() < 0.85:
        received_stamp(img, stamp_xy)


# ---------------------------------------------------------------- templates

def tpl_fund_commitment(p):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    fund = random.choice(FUNDS)
    logo(d, (W - 60, 50), fund, "מחוז " + random.choice(["צפון", "דרום", "מרכז", "ירושלים"]))
    ltr(d, (60, 60), f"*{random.randint(1000,9999)}  :מוקד", ARIAL(22))
    commit_no = str(random.randint(700000000, 799999999))
    d.rectangle([60, 150, 180, 200], outline=(0, 0, 0), width=3)
    heb(d, (165, 158), "מקור", ARIALB(30))
    heb(d, (W - 60, 150), f"תאריך הפקה: {rdate()}", ARIAL(24))
    heb(d, (W - 200, 230), "התחייבות לתשלום עבור שירותי בריאות", ARIALB(44))
    heb(d, (W - 330, 295), "התחייבות מספר", ARIALB(30))
    w = d.textlength(commit_no, font=ARIALB(34))
    d.text((W - 360 - 230 - w + 60, 292), commit_no, font=ARIALB(34), fill=(0, 0, 0))
    highlight(img, (W - 360 - 230 - w + 50, 288, W - 360 - 230 + 70, 332))
    d = ImageDraw.Draw(img)
    heb(d, (W - 60, 370), f"תאריך הטיפול: {rdate()}", ARIALB(26))
    # provider block
    d.rectangle([60, 410, W - 60, 640], outline=(0, 0, 0), width=2)
    heb(d, (W - 75, 418), "נותן השירות", ARIALB(26))
    d.line([(60, 455), (W - 60, 455)], fill=(0, 0, 0), width=1)
    hosp = random.choice(HOSPITALS)
    rows = [("שם", hosp), ("מחלקה / מרפאה", "המעבדה האזורית לנגיפים"),
            ("כתובת", f"רח' {random.choice(STREETS)} {random.randint(1,120)} {random.choice(CITIES)}"), ("טלפון", phone())]
    for i, (k, v) in enumerate(rows):
        heb(d, (W - 75, 470 + i * 40), k, ARIALB(24))
        heb(d, (W - 300, 470 + i * 40), ": " + v, COUR(24))
    # service table
    test, code = random.choice(TESTS)
    y0 = 680
    d.rectangle([60, y0, W - 60, y0 + 100], outline=(0, 0, 0), width=2)
    d.line([(60, y0 + 45), (W - 60, y0 + 45)], fill=(0, 0, 0))
    for x in (180, 380):
        d.line([(x, y0), (x, y0 + 100)], fill=(0, 0, 0))
    heb(d, (170, y0 + 8), "כמות", ARIALB(24))
    heb(d, (370, y0 + 8), "קוד השירות", ARIALB(24))
    heb(d, (W - 75, y0 + 8), "שם השירות", ARIALB(24))
    d.text((105, y0 + 55), "1", font=COUR(26), fill=(0, 0, 0))
    d.text((240, y0 + 55), code, font=COUR(26), fill=(0, 0, 0))
    heb(d, (W - 75, y0 + 55), "בדיקת מעבדה וירולוגית", COUR(24))
    hand(img, (420, y0 - 50), test, size=48, hebrew=False)
    d = ImageDraw.Draw(img)
    heb(d, (W - 60, 810), "התחייבות בטופס זה היא רק עבור השירותים המופיעים לעיל, ורק למוסד הרפואי הנ\"ל.", ARIALB(24))
    para = ["ניתן להגיש בקשה לביטול התחייבות זו או לקבלת התחייבות חדשה באתר הקופה או במוקד הטלפוני.",
            "יש להציג טופס זה בעת קבלת השירות. הטופס תקף רק עם חותמת ונתוני המבוטח.",
            "לתשומת לבך: ההתחייבות לא תממן טיפול כפול באותו שירות.",
            "אם אינך משתמש/ת בהתחייבות, אנא החזר/י אותה לקופה."]
    for i, s in enumerate(para):
        heb(d, (W - 60, 860 + i * 36), s, ARIAL(22))
    # member details
    fn, ln = p["name"]
    y = 1290
    d.line([(60, y - 10), (W - 60, y - 10)], fill=(0, 0, 0), width=2)
    heb(d, (W - 60, y), "פרטי המבוטח/ת", ARIALB(26))
    heb(d, (W - 60, y + 45), "ת\"ז", ARIALB(24))
    heb(d, (W - 60, y + 85), "שם", ARIALB(24))
    heb(d, (W - 60, y + 125), f"כתובת: {random.choice(STREETS)} {random.randint(1,99)} {random.choice(CITIES)}", ARIAL(22))
    heb(d, (500, y + 45), f"תאריך לידה: {p['birth']}", ARIAL(22))
    heb(d, (500, y + 85), f"טלפונים: {mobile()}", ARIAL(22))
    # handwritten id / name (the masked-looking fields in the originals)
    hand(img, (W - 420, y + 30), p["id"], size=46, hebrew=False)
    hand(img, (W - 520, y + 72), f"{fn} {ln}", size=50)
    d = ImageDraw.Draw(img)
    heb(d, (W - 60, y + 190), f"תוקף התחייבות זו עד תאריך {rdate(2027)}", ARIALB(24))
    heb(d, (W - 60, y + 230), f"מפיק/ת: {random.choice(DOCTORS)}", ARIAL(22))
    received_stamp(img, (330, 1100))
    if random.random() < 0.7:
        hand(img, (100, 1180), random.choice(SAMPLES), size=70)
    barcode(img, (60, 60 + 50), w=160, h=45, label=str(random.randint(930000, 949999)))
    footer(ImageDraw.Draw(img))
    return img


def tpl_hospital_screen(p):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    grey = (120, 120, 120)
    d.text((80, 40), rdate(), font=ARIAL(22), fill=(0, 0, 0))
    d.text((80, 68), rdate(), font=ARIAL(22), fill=(0, 0, 0))
    heb(d, (330, 40), "ביק.ראש.", ARIALB(22))
    heb(d, (330, 68), "אחר.", ARIALB(22))
    d.text((640, 30), p["birth"], font=ARIALB(30), fill=(0, 0, 0))
    heb(d, (W - 80, 40), "מין", ARIALB(24))
    heb(d, (W - 80, 70), "מקרה", ARIALB(24))
    heb(d, (720, 75), random.choice(["זכר", "נקבה"]), ARIAL(22))
    d.text((640, 100), str(random.randint(30000000, 39999999)), font=ARIAL(22), fill=(0, 0, 0))
    hand(img, (W - 190, 8), f"{p['id']} - {p['name'][0]}", size=40, anchor_right=True)
    # form grid
    rows = ["נתוני ביקור", "סוג מקרה", "סוג ביקור", "תאריך", "קטגוריית טיפול", "משך שהות מוערך",
            "סוג מבקר", "הערה", "גורם מפנה", "", "שיוך ארגוני", "מח.סיעודית", "חדר טיפולים"]
    for i, r in enumerate(rows):
        y = 170 + i * 42
        heb(d, (W - 80, y), r, ARIAL(22), (0, 0, 0) if i else (0, 0, 0))
    def field(x0, y, w, txt, bold=False):
        d.rectangle([x0, y - 2, x0 + w, y + 28], outline=(170, 170, 170))
        heb(d, (x0 + w - 6, y), txt, ARIALB(20) if bold else ARIAL(20))
    field(760, 212, 220, "חולה אמבולטורי")
    field(760, 254, 220, "ביקור במרפאה  01")
    dt = rdate()
    field(760, 296, 220, dt)
    highlight(img, (780, 296, 970, 324)); d = ImageDraw.Draw(img)
    field(560, 212, 120, "תחום", True)
    field(560, 254, 120, "סיבת ביקור")
    field(560, 296, 120, f"{random.randint(7,17):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}")
    fund = random.choice(FUNDS)
    field(760, 506, 220, f"{random.randint(10,20)}  {fund.split()[-1]}")
    highlight(img, (770, 506, 900, 534)); d = ImageDraw.Draw(img)
    field(860, 422, 120, "1  אזרח")
    heb(d, (700, 506), "בי\"ח מפנה", ARIAL(20), (0, 0, 180))
    heb(d, (500, 212), "שער אמבולטורי", ARIAL(20))
    heb(d, (220, 212), "מקרה חירום", ARIAL(20))
    heb(d, (300, 254), "סטאטוס   בפועל", ARIAL(20))
    heb(d, (960, 630), f"{random.choice(DEPTS)}", ARIAL(20))
    heb(d, (700, 630), "מח.רפואית", ARIAL(20), (0, 0, 180))
    # insurance strip
    y = 780
    d.line([(60, y), (W - 60, y)], fill=grey)
    heb(d, (W - 80, y + 10), "קשרי ביטוח - סקירה", ARIAL(22))
    d.rectangle([60, y + 45, W - 60, y + 80], fill=(235, 235, 240), outline=grey)
    heb(d, (W - 80, y + 50), "מבוטח   שם מבוטח   מבוטח מתא.  מבוטח עד   מספר התחייבות", ARIAL(20))
    commit_no = str(random.randint(700000000, 799999999))
    heb(d, (W - 80, y + 95), f"{random.randint(110000,119999)}   {fund} {random.choice(CITIES)}   {rdate()}  {rdate()}", ARIAL(20))
    cw = d.textlength(commit_no, font=ARIAL(20))
    d.rectangle([60, y + 92, 80 + cw, y + 122], fill="white")
    d.text((70, y + 95), commit_no, font=ARIAL(20), fill=(0, 0, 0))
    highlight(img, (64, y + 92, 76 + cw, y + 122))
    barcode(img, (W - 300, 1250), w=200, h=60)
    if random.random() < .7:
        received_stamp(img, (700, 1350))
    highlight(img, (W - 520, y + 45, W - 380, y + 78))
    for i in range(4):
        ImageDraw.Draw(img).rectangle([520, y + 130 + i * 30, 560, y + 155 + i * 30], outline=grey)
    # handwritten side note: lab number + date
    hand(img, (70, 330), "מספר מתג'", size=46, angle=random.uniform(5, 12))
    hand(img, (80, 390), str(random.randint(930000, 949999)), size=52, hebrew=False, angle=random.uniform(4, 10))
    hand(img, (95, 450), dt[:5].replace(".", "/"), size=50, hebrew=False, angle=random.uniform(4, 10))
    footer(ImageDraw.Draw(img))
    return img


def tpl_lab_referral(p):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    lab = random.choice(LABS)
    heb(d, (W - 220, 60), lab, ARIALB(42))
    highlight(img, (300, 55, W - 210, 110)); d = ImageDraw.Draw(img)
    heb(d, (W - 220, 118), f"רח' {random.choice(STREETS)} {random.randint(1,90)} {random.choice(CITIES)}  טל. {phone()}  פקס. {phone()}", ARIAL(20))
    d.line([(150, 150), (W - 150, 150)], fill=(0, 0, 0), width=3)
    barcode(img, (W - 190, 40), w=130, h=55)
    hand(img, (120, 190), rdate().replace(".", "/"), size=46, hebrew=False)
    heb(d, (520, 200), random.choice(CITIES), ARIAL(26))
    d.line([(100, 245), (480, 245)], fill=(0, 0, 0))
    heb(d, (W - 150, 290), "הפניה/ התחייבות לבדיקות  במעבדת:", ARIALB(32))
    d.line([(150, 330), (640, 330)], fill=(0, 0, 0))
    hand(img, (220, 260), random.choice(["וירולוגיה", "בית החולים", "מעבדה מרכזית"] + DEPTS), size=46)
    d = ImageDraw.Draw(img)
    heb(d, (W - 120, 400), "1. שם:", ARIALB(26))
    d.line([(640, 430), (W - 210, 430)], fill=(0, 0, 0))
    heb(d, (560, 400), "ת. זהות:", ARIALB(26))
    d.line([(150, 430), (440, 430)], fill=(0, 0, 0))
    # patient sticker
    sx, sy = 120, 460
    d.rectangle([sx, sy, sx + 420, sy + 130], outline=(0, 0, 0), width=2)
    d.rectangle([sx, sy, sx + 420, sy + 30], fill=(0, 0, 0))
    d.text((sx + 10, sy + 4), f"{random.randint(1000,9999)}  {lab.split()[1].upper() if False else 'MEDICAL LAB.'}", font=ARIALB(18), fill="white")
    d.text((sx + 10, sy + 42), f"D.O.B: {p['birth'].replace('.', '/')}", font=ARIALB(22), fill=(0, 0, 0))
    d.text((sx + 10, sy + 78), "ID / PASS:", font=ARIALB(22), fill=(0, 0, 0))
    hand(img, (sx + 150, sy + 62), p["id"], size=40, hebrew=False)
    hand(img, (sx + 20, sy + 98), p["name"][1], size=34)
    d = ImageDraw.Draw(img)
    heb(d, (W - 120, 480), "ת.ל. / גיל:", ARIALB(24))
    heb(d, (W - 150, 640), "נא קבלו את דוגמאות הנבדק לעיל ובצעו בהן את הבדיקות הבאות:", ARIALB(26))
    heb(d, (W - 380, 720), "פרופיל וירולוגי " + str(random.randint(1000, 2000)), ARIALB(30))
    heb(d, (W - 450, 780), "תוספת פרופיל שומנים", ARIALB(28))
    heb(d, (W - 100, 870), "אחר:", ARIALB(26))
    d.line([(150, 900), (W - 170, 900)], fill=(0, 0, 0))
    tests = random.sample(TESTS, random.randint(1, 3))
    for i, (t, _) in enumerate(tests):
        hand(img, (220 + random.randint(-30, 60), 830 + i * 70), t.title() if random.random() < .5 else t, size=random.randint(50, 64), hebrew=False)
    if random.random() < 0.6:
        hand(img, (680, 960), random.choice(["דחוף!", "לשלוח תשובה לרופא", "בהריון - שבוע " + str(random.randint(8, 36)), "לבירור חום"]), size=50)
    hand(img, (120, 1050), random.choice(SAMPLES), size=78)
    if random.random() < .8:
        received_stamp(img, (900, 1080))
    d = ImageDraw.Draw(img)
    heb(d, (W - 150, 1250), "יש לכלול את מס' הקליטה בשדה אסמכתא בכל דף תוצאה", ARIALB(30))
    d.line([(160, 1290), (W - 150, 1290)], fill=(0, 0, 0), width=2)
    for i, s in enumerate(["בכל בעיה שהיא יש להתקשר למעבדה השולחת. אין להשמיד דגימות מבלי ליידע את המעבדה.",
                           "דגימות לאחר טיפול יוחזרו בתום הבדיקה. עובדי המעבדה זמינים לכל בירור."]):
        heb(d, (W - 150, 1310 + i * 32), s, ARIAL(22))
    d.rectangle([150, 1410, W - 150, 1530], outline=(0, 0, 0), width=3)
    ltr(d, (230, 1425), "results@example-lab.test", ARIALB(32))
    heb(d, (W - 180, 1430), "את התשובות נא שלוח/י ל-", ARIAL(24))
    heb(d, (W - 180, 1475), f"או בפקס למעבדה {phone()}  בהקדם האפשרי", ARIALB(28))
    heb(d, (W - 150, 1560), "נא חייבו חשבוננו אצלכם", ARIALB(26))
    heb(d, (420, 1600), "בתודה - צוות המעבדה", ARIAL(22))
    footer(ImageDraw.Draw(img))
    return img


def tpl_hospital_request(p):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    hosp = random.choice(HOSPITALS)
    col = random.choice([(0, 70, 140), (110, 20, 60), (20, 100, 70)])
    logo(d, (W - 60, 40), hosp, "המעבדה לחקר נגיפים", col)
    d.line([(60, 130), (W - 60, 130)], fill=col, width=3)
    heb(d, (W - 60, 150), rdate().replace(".", "/"), ARIAL(22))
    heb(d, (W - 60, 200), "לכבוד:", ARIAL(24))
    heb(d, (W - 60, 235), "המעבדה האזורית לנגיפים - המרכז הרפואי המשולב", ARIAL(24))
    heb(d, (W - 60, 300), "הנדון: בקשה לשליחת בדיקה לגורם חוץ (מעבדה חיצונית) - התחייבות כספית", ARIALB(26))
    d.line([(400, 330), (W - 60, 330)], fill=(0, 0, 0))
    heb(d, (W - 60, 360), "אבקשכם לבצע את הבדיקה המצוינת מטה על חשבון המרכז הרפואי שלנו.", ARIAL(22))
    fn, ln = p["name"]
    test, code = random.choice(TESTS)
    blocks = [("פרטי הנבדק:", None), ("שם המשפחה:", None), ("שם פרטי:", None), ("תעודת זהות:", None), ("גורם שולח:", random.choice(DEPTS)),
              ("", None), ("פרטי הדגימה:", None), ("מספר דגימה:", str(random.randint(944000000, 944999999))),
              ("הבדיקה הנדרשת:", test), ("סוג הדגימה:", random.choice(SAMPLES)), ("תאריך לקיחת חומר:", rdate()),
              ("", None), ("תשלום:", None), ("מק\"ט מוצר:", code), ("כמות לחיוב:", str(random.randint(1, 3)))]
    y = 420
    for k, v in blocks:
        if k:
            heb(d, (W - 60, y), k, ARIALB(22) if v is None and k.endswith(":") and k in ("פרטי הנבדק:", "פרטי הדגימה:", "תשלום:") else ARIAL(22))
            if v:
                heb(d, (W - 330, y), v, ARIAL(22) if any("\u0590" <= c <= "\u05ff" for c in v) else ARIAL(22))
        y += 36
    hand(img, (W - 330, 438), ln, size=42, anchor_right=True, angle=random.uniform(-3, 3))
    hand(img, (W - 330, 476), fn, size=42, anchor_right=True, angle=random.uniform(-3, 3))
    hand(img, (W - 330, 506), p["id"], size=34, hebrew=False, anchor_right=True, angle=random.uniform(-3, 3))
    d = ImageDraw.Draw(img)
    heb(d, (520, 900), "שימו לב!", ARIALB(22))
    heb(d, (520, 930), "מספר הדרישה מהווה מספר התחייבות", ARIALB(22))
    heb(d, (520, 960), "בדיקות שלא תוזמנו בטופס זה לא ישולמו", ARIALB(22))
    heb(d, (W - 60, 1000), "יש להעביר את החיוב להנהלת בית החולים עם ציון מספר טופס זה.", ARIAL(22))
    heb(d, (W - 60, 1200), "בברכה,", ARIAL(22))
    doc = random.choice(DOCTORS)
    heb(d, (W - 60, 1250), doc, ARIALB(24))
    heb(d, (W - 60, 1280), "מנהל/ת המעבדה", ARIAL(20))
    scribble_signature(img, (W - 380, 1240))
    no = f"{random.randint(100, 999):06d}"
    d = ImageDraw.Draw(img)
    d.rectangle([60, 1300, 260, 1360], outline=(0, 0, 0), width=2)
    d.text((80, 1310), no, font=ARIALB(34), fill=(0, 0, 0))
    highlight(img, (70, 1305, 250, 1355))
    hand(img, (330, 1300), f"{p['id']}  {fn}", size=40)
    if random.random() < 0.8:
        received_stamp(img, (330, 1130))
    hand(img, (120, 700), random.choice(SAMPLES), size=80)
    d = ImageDraw.Draw(img)
    d.line([(60, 1620), (W - 60, 1620)], fill=col)
    heb(d, (W - 60, 1630), f"נא לשלוח תשובה לפקס: {phone()}   בכל שאלה ניתן לפנות לטלפון: {phone()}", ARIAL(20))
    footer(ImageDraw.Draw(img))
    return img


def tpl_rotated_list(p):
    """Landscape lab work-list scanned sideways."""
    LW, LH = H, W
    img = Image.new("RGB", (LW, LH), "white")
    d = ImageDraw.Draw(img)
    heb(d, (LW - 60, 40), "דוח רשימת עבודה לפי בדיקה", ARIALB(36))
    heb(d, (LW - 60, 90), f"הופק: {rdate()} {random.randint(8,18):02d}:{random.randint(0,59):02d}", ARIAL(22))
    cols = ["מס' דרישה", "ת.ז.", "שם", "תאריך לידה", "בדיקה", "סוג דגימה", "קופה", "הערות"]
    xs = [LW - 60 - i * 205 for i in range(len(cols))]
    y = 150
    d.rectangle([60, y - 5, LW - 60, y + 35], fill=(225, 225, 225))
    for x, c in zip(xs, cols):
        heb(d, (x - 5, y), c, ARIALB(22))
    entries = [p] + [make_patient() for _ in range(random.randint(5, 9))]
    for i, e in enumerate(entries):
        y = 200 + i * 75
        d.line([(60, y + 55), (LW - 60, y + 55)], fill=(180, 180, 180))
        test, _ = random.choice(TESTS)
        vals = [str(random.randint(200000000, 299999999)), e["id"], " ".join(e["name"]), e["birth"], test[:14],
                random.choice(SAMPLES), random.choice(FUNDS).split()[-1], ""]
        for x, v in zip(xs, vals):
            if any("\u0590" <= c <= "\u05ff" for c in v):
                heb(d, (x - 5, y + 10), v, ARIAL(20))
            else:
                d.text((x - 5 - d.textlength(v, font=ARIAL(20)), y + 10), v, font=ARIAL(20), fill=(0, 0, 0))
        if random.random() < 0.4:
            highlight(img, (xs[1] - 190, y + 5, xs[1], y + 40)); d = ImageDraw.Draw(img)
        if random.random() < 0.5:
            hand(img, (90, y - 5), random.choice(["נשלח", "חסר", "לחזור", "OK", "בוצע"]), size=40)
            d = ImageDraw.Draw(img)
    hand(img, (300, LH - 220), f"{rdate()[:5]}  " + random.choice(["נבדק", "התקבל"]), size=56)
    img = img.rotate(90, expand=True)
    img = img.resize((W, H))
    barcode(img, (W - 280, 60), w=180, h=55)
    footer(ImageDraw.Draw(img))
    return img


def make_patient():
    return {"name": random.choice(PATIENTS), "id": rid(), "birth": rbirth()}


TEMPLATES = [tpl_fund_commitment, tpl_hospital_screen, tpl_lab_referral, tpl_hospital_request, tpl_rotated_list]

if __name__ == "__main__":
    out = sys.argv[1]
    pages = []
    names = list(PATIENTS)
    random.shuffle(names)
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    for i in range(n):
        p = {"name": names[i % len(names)], "id": rid(), "birth": rbirth()}
        tpl = TEMPLATES[i % len(TEMPLATES)] if i < len(TEMPLATES) else random.choice(TEMPLATES)
        pages.append(scan_effects(tpl(p)))
        print(i + 1, tpl.__name__, " ".join(p["name"]))
    pages[0].save(out, save_all=True, append_images=pages[1:], resolution=150)
    for i, pg in enumerate(pages[:5]):
        pg.resize((620, 877)).save(os.path.join(HERE, f"prev{i}.png"))
