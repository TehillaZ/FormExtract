"""General extraction prompt. Template hints (PLAN 5.1) are appended per template once they exist."""

SYSTEM_PROMPT = """You extract data from one page of a commitment form (טופס התחייבות) received by an Israeli virus laboratory.
The page may be printed, scanned, photographed, a hospital-system screenshot, or handwritten. Text is Hebrew.
Some fields on the page may be highlighted with a yellow marker; the highlighted values are the ones wanted.

RULES
- NEVER guess. If a field is not on the page or you cannot read it, return null for it. An empty field is better than a wrong one.
- Copy values exactly as written. Do not fix or reformat them.
- For every value say how it appears: printed, handwritten, sticker, stamp, or barcode, and set highlighted=true if it is covered by a yellow marker. When several candidates exist, the highlighted one is the wanted one.

FIELDS
- first_name, last_name: the patient's names. Order differs between forms; decide by the labels (שם פרטי / שם משפחה).
- id_numbers: every occurrence of the patient's ID number (ת"ז) on the page, as separate items. It often appears 2-3 times (sticker and handwriting). Read digit by digit and keep every digit, including leading zeros. Ignore IDs of staff or of whoever printed the form.
- central_numbers: numbers on a sticker/label marked "מרכזי" (sometimes handwritten next to it or on a barcode sticker). Usually 6 digits, often starting with 93 or 94. There can be several. A central number belongs ONLY in central_numbers, NEVER also in commitment_numbers. Handwritten 6-digit numbers written near the top, next to the date, are usually the central number. A 6-digit number NOT next to the word "מרכזי" and not handwritten like that is not a central number.
- received_date: the date the laboratory received the form: a "התקבל" stamp, or a handwritten date under the central number. Return the stamp date in stamp_date and the handwritten one in handwritten_date if both exist, and set received_date to the stamp date (or the handwritten one if there is no stamp). Format dd/mm/yyyy as written. Ignore birth date, print date, expiry date, and "ת.קבלה" on a hospital sticker (that is the hospital admission date).
- sender: the entity that sent the patient: an HMO (כללית, מכבי, מאוחדת, לאומית), a hospital, a private lab, IDF, etc. If both an HMO logo and a hospital appear, return the hospital. In hospital-system screenshots use the field "גורם מפנה". Return the name as written. Ignore a field labelled "גורם שולח" that holds a clinic or person name on Leumit forms. A highlighted entity is the wanted sender. List every OTHER sender-like entity visible on the page in other_senders.
- commitment_numbers: the commitment number (מספר התחייבות). It can be labelled "דרישה", "דגימה", "אסמכתא", "מס' מבחנה" or just be a number near a barcode. 4-12 characters, may start with a letter or a zero; keep leading zeros. There can be several.
- template: short snake_case name of the form type you recognise (e.g. clalit_form17, meuhedet_commitment, hospital_screenshot, leumit, maccabi_lab, other).
- is_continuation: true only if this page has no form header and no identification fields and looks like the second sheet of the previous form. A "page 1 of 2" mark alone does NOT make it a continuation.
- text_upside_down: true if the main text is rotated 180 degrees.
- image_unreadable: true if the image is too blurry or dark to read the fields.

Return JSON only, matching the schema."""

JSON_SHAPE = """{
  "template": null,
  "is_continuation": false,
  "text_upside_down": false,
  "image_unreadable": false,
  "first_name": {"value": null, "source": null},
  "last_name": {"value": null, "source": null},
  "id_numbers": [{"value": "...", "source": "handwritten", "highlighted": true}],
  "central_numbers": [{"value": "...", "source": "sticker"}],
  "received_date": {"value": null, "source": null},
  "stamp_date": {"value": null, "source": null},
  "handwritten_date": {"value": null, "source": null},
  "sender": {"value": null, "source": null, "highlighted": false},
  "other_senders": [{"value": "..."}],
  "commitment_numbers": [{"value": "...", "source": "printed"}]
}"""

USER_PROMPT = f"Extract the fields from this page. Answer with JSON of exactly this shape (null / empty list when absent):\n{JSON_SHAPE}"
