"""Fase 2: quanto do conteudo esta em imagem, e nao em texto.

Na p.160 o corpo inteiro da secao e imagem colada no Word; so o titulo e as
notas de rodape sao texto. Contar "paginas sem texto" nao apanha isso.
Aqui se mede a AREA de imagem dentro da mancha e o texto de corpo por pagina.
"""
import json
from pathlib import Path

import pymupdf

BASE = Path(__file__).parent
doc = pymupdf.open(BASE / "bruto" / "TCU_Licitacoes_Contratos_5ed_2025.pdf")

# A4 = 595 x 842 pt. Mancha util aproximada, fora cabecalho e rodape.
MANCHA = pymupdf.Rect(70, 60, 545, 760)
AREA_MANCHA = MANCHA.get_area()

regs = []
for i, page in enumerate(doc, 1):
    d = page.get_text("dict")
    area_img = 0.0
    n_img = 0
    chars_corpo = 0
    chars_nota = 0
    for b in d["blocks"]:
        r = pymupdf.Rect(b["bbox"]) & MANCHA
        if b["type"] == 1:
            if not r.is_empty:
                area_img += r.get_area()
                n_img += 1
            continue
        for line in b["lines"]:
            for sp in line["spans"]:
                n = len(sp["text"].strip())
                if sp["size"] < 9.5:
                    chars_nota += n
                else:
                    chars_corpo += n
    regs.append({
        "p": i,
        "corpo": chars_corpo,
        "nota": chars_nota,
        "n_img": n_img,
        "area_img_pct": round(100 * area_img / AREA_MANCHA, 1),
    })

Path(BASE / "medicao" / "imagens.json").write_text(
    json.dumps(regs, ensure_ascii=False), encoding="utf-8")

faixas = [(0, 1), (1, 10), (10, 25), (25, 50), (50, 200)]
print("distribuicao da area de imagem na mancha:")
for a, b in faixas:
    sel = [r for r in regs if a <= r["area_img_pct"] < b]
    print(f"  {a:>3}-{b:<3}% da mancha : {len(sel):>5} paginas")

crit = [r for r in regs if r["area_img_pct"] >= 10 or r["corpo"] < 400]
print(f"\npaginas com >=10% de imagem OU <400 chars de corpo: {len(crit)}")
print(f"  destas, com corpo < 400 chars: "
      f"{sum(1 for r in crit if r['corpo'] < 400)}")
print(f"chars de corpo totais : {sum(r['corpo'] for r in regs):,}")
print(f"chars de nota totais  : {sum(r['nota'] for r in regs):,}")

print("\n40 paginas com mais area de imagem:")
for r in sorted(regs, key=lambda x: -x["area_img_pct"])[:40]:
    print(f"  p{r['p']:>5}  img {r['area_img_pct']:>5.1f}%  "
          f"n={r['n_img']:>3}  corpo={r['corpo']:>5}  nota={r['nota']:>5}")
