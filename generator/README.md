# Synthetic form generator

Makes a PDF of fictional commitment forms (printed text, handwriting, yellow highlights, stamps, barcodes, scan
noise, sideways pages) so the system can be tried and demonstrated **without any patient data**. Every name,
ID number and commitment number is made up and random.

```
pip install pillow python-bidi
python generator/gen.py OUT.pdf [SEED] [PAGES]
python generator/gen.py demo.pdf 7 20      # 20 pages, always the same for seed 7
```

Then upload the PDF in the app. It also writes small preview images `prev0.png` to `prev4.png` next to the script
(they are git-ignored).

- **Windows only as it stands:** the printed text uses Arial, David and Courier New from `C:/Windows/Fonts/`. They are
  not stored in this repository. On another system, change the `WF` path or the font names at the top of `gen.py`.
- **Handwriting fonts** in `fonts/` are Google Fonts (Amatic SC, Caveat, Karantina, Suez One, Gveret Levin), which
  Google publishes under open licences. Check each font's licence on fonts.google.com before redistributing.
- The generated IDs are random 9-digit numbers: about one in ten passes the ID check digit, so they behave like the
  development samples.
