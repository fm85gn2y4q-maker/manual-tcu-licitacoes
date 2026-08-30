"""Medicao fase 1: camada de texto, sumario embutido, imagens, fontes.

Nao extrai o acervo. Serve para decidir a estrategia de extracao antes de
gastar tempo com ela: se ha pagina sem texto, se o PDF traz outline, e como
o TCU marca visualmente a caixa de jurisprudencia.
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import pymupdf

BASE = Path(__file__).parent
PDF = BASE / "bruto" / "TCU_Licitacoes_Contratos_5ed_2025.pdf"
MED = BASE / "medicao"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main() -> int:
    MED.mkdir(exist_ok=True)
    doc = pymupdf.open(PDF)

    paginas = []
    fontes = Counter()
    tamanhos = Counter()
    cores = Counter()
    sem_texto = []
    for i, page in enumerate(doc, 1):
        txt = page.get_text("text")
        d = page.get_text("dict")
        n_img = len([b for b in d["blocks"] if b["type"] == 1])
        n_span = 0
        for b in d["blocks"]:
            if b["type"] != 0:
                continue
            for line in b["lines"]:
                for sp in line["spans"]:
                    n_span += 1
                    fontes[sp["font"]] += len(sp["text"])
                    tamanhos[round(sp["size"], 1)] += len(sp["text"])
                    cores[sp["color"]] += len(sp["text"])
        reg = {
            "p": i,
            "chars": len(txt.strip()),
            "imgs": n_img,
            "spans": n_span,
            "desenhos": len(page.get_drawings()),
        }
        paginas.append(reg)
        if reg["chars"] < 20:
            sem_texto.append(reg)

    outline = doc.get_toc(simple=False)

    rel = {
        "arquivo": PDF.name,
        "sha256": sha256(PDF),
        "mb": round(PDF.stat().st_size / 1e6, 2),
        "paginas": doc.page_count,
        "metadata": doc.metadata,
        "chars_total": sum(p["chars"] for p in paginas),
        "chars_por_pagina": round(sum(p["chars"] for p in paginas) / doc.page_count, 1),
        "paginas_sem_texto": len(sem_texto),
        "detalhe_sem_texto": sem_texto,
        "paginas_com_imagem": sum(1 for p in paginas if p["imgs"]),
        "imagens_total": sum(p["imgs"] for p in paginas),
        "outline_entradas": len(outline),
        "outline_amostra": outline[:40],
        "fontes_top": fontes.most_common(20),
        "tamanhos_top": tamanhos.most_common(20),
        "cores_top": [(hex(c), n) for c, n in cores.most_common(15)],
    }
    (MED / "fase1.json").write_text(
        json.dumps(rel, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (MED / "paginas.json").write_text(
        json.dumps(paginas, ensure_ascii=False), encoding="utf-8")

    for k in ("arquivo", "sha256", "mb", "paginas", "chars_total",
              "chars_por_pagina", "paginas_sem_texto", "paginas_com_imagem",
              "imagens_total", "outline_entradas"):
        print(f"{k:24} {rel[k]}")
    print("metadata:", rel["metadata"])
    print("\nfontes (chars):")
    for f, n in rel["fontes_top"][:12]:
        print(f"  {f:44} {n:>9,}")
    print("\ntamanhos (chars):")
    for s, n in rel["tamanhos_top"][:12]:
        print(f"  {s:>6} {n:>9,}")
    print("\ncores (chars):")
    for c, n in rel["cores_top"][:10]:
        print(f"  {c:>10} {n:>9,}")
    print("\npaginas sem texto:", [p["p"] for p in sem_texto])
    return 0


if __name__ == "__main__":
    sys.exit(main())
