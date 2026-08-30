"""Coleta a versao interativa do manual pela API REST do WordPress do TCU.

Por que nao o PDF: no PDF publicado o corpo de ~160 paginas foi colado no Word
como IMAGEM (p. ex. a p. 149 impressa, com os principios do art. 5o da
Lei 14.133/2021, nao tem uma letra de texto). A versao interativa traz o mesmo
conteudo em texto nativo, com as notas de rodape e os quadros em tabela.

Grava o JSON cru de cada post. Nao interpreta nada aqui: a interpretacao fica
em montar.py, para poder refazer sem baixar de novo.
"""
import json
import sys
import time
from pathlib import Path

import requests

BASE = Path(__file__).parent
CRU = BASE / "bruto" / "wp"
API = "https://licitacoesecontratos.tcu.gov.br/wp-json/wp/v2"
UA = {"User-Agent": "Mozilla/5.0 (acervo juridico; coleta de publicacao oficial)"}


def baixar(tipo: str) -> list:
    itens, pagina = [], 1
    while True:
        r = requests.get(f"{API}/{tipo}", headers=UA, timeout=60,
                         params={"per_page": 100, "page": pagina,
                                 "orderby": "id", "order": "asc"})
        if r.status_code == 400:
            break
        r.raise_for_status()
        lote = r.json()
        if not lote:
            break
        itens.extend(lote)
        total = int(r.headers.get("x-wp-totalpages", 1))
        print(f"  {tipo} pagina {pagina}/{total}: +{len(lote)} (total {len(itens)})")
        if pagina >= total:
            break
        pagina += 1
        time.sleep(0.4)
    return itens


def main() -> int:
    CRU.mkdir(parents=True, exist_ok=True)
    inventario = {}
    for tipo in ("posts", "pages"):
        itens = baixar(tipo)
        (CRU / f"{tipo}.json").write_text(
            json.dumps(itens, ensure_ascii=False), encoding="utf-8")
        inventario[tipo] = len(itens)
        print(f"{tipo}: {len(itens)} gravados")

    posts = json.loads((CRU / "posts.json").read_text(encoding="utf-8"))
    chars = sum(len(p["content"]["rendered"]) for p in posts)
    mods = sorted(p["modified"] for p in posts)
    print(f"\nhtml total: {chars:,} chars")
    print(f"modificado de {mods[0]} a {mods[-1]}")
    (BASE / "medicao" / "coleta.json").write_text(
        json.dumps({"inventario": inventario, "html_chars": chars,
                    "modified_min": mods[0], "modified_max": mods[-1]},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
