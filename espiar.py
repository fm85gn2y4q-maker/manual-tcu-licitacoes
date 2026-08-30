import sys
import pymupdf
doc = pymupdf.open("bruto/TCU_Licitacoes_Contratos_5ed_2025.pdf")
for n in [int(x) for x in sys.argv[1:]]:
    page = doc[n - 1]
    print("=" * 78)
    print("PAGINA", n)
    print("=" * 78)
    d = page.get_text("dict")
    for b in d["blocks"]:
        if b["type"] == 1:
            print(f"  [IMAGEM {b['bbox']}]")
            continue
        for line in b["lines"]:
            for sp in line["spans"]:
                t = sp["text"]
                if not t.strip():
                    continue
                print(f"  [{sp['font'][:22]:22} {sp['size']:5.1f} "
                      f"{hex(sp['color']):>9} x={sp['bbox'][0]:6.1f}] {t[:110]}")
