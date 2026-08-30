"""Levanta a gramatica real dos rotulos e a marcacao dos quadros de risco.

Regra aprendida em acervo anterior: nao escrever a regex antes de olhar o
corpus. Aqui se lista o que de fato aparece.
"""
import json
import re
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

BASE = Path(__file__).parent
posts = json.loads((BASE / "bruto" / "wp" / "posts.json").read_text(encoding="utf-8"))

# 1) como o HTML marca um quadro de riscos
achou = 0
for p in posts:
    soup = BeautifulSoup(p["content"]["rendered"], "lxml")
    for el in soup.find_all(string=re.compile(r"Riscos relacionados", re.I)):
        pai = el.find_parent(["p", "td", "th", "li", "h1", "h2", "h3"])
        if pai is None:
            continue
        achou += 1
        if achou > 2:
            break
        print("=" * 70)
        print("SECAO:", p["title"]["rendered"][:60])
        print("tag da legenda:", pai.name, "| classe:", pai.get("class"))
        print("texto:", pai.get_text(" ", strip=True)[:100])
        seg = pai
        for _ in range(6):
            seg = seg.find_next_sibling()
            if seg is None:
                break
            print(f"  irmao -> <{seg.name} class={seg.get('class')}> "
                  f"{seg.get_text(' ', strip=True)[:150]}")
    if achou > 2:
        break

# 2) gramatica dos rotulos da primeira coluna dos quadros de jurisprudencia
print("\n" + "=" * 70)
print("GRAMATICA DOS ROTULOS")
LEG = re.compile(r"(Quadro|Figura|Tabela)\s*(\d+)\s*[–—-]\s*(.+)$", re.I)
formas = Counter()
exemplos = {}
for p in posts:
    soup = BeautifulSoup(p["content"]["rendered"], "lxml")
    leg = None
    for el in soup.find_all(["p", "table"]):
        if el.name == "p":
            m = LEG.match(el.get_text(" ", strip=True))
            leg = m.group(3).strip() if m else leg
            continue
        if not leg or not leg.lower().startswith("jurisprud"):
            continue
        for tr in el.find_all("tr")[1:]:
            tds = tr.find_all(["td", "th"])
            if len(tds) < 2:
                continue
            rot = tds[0].get_text(" ", strip=True)
            # normaliza para uma "forma": digitos -> N, palavras mantidas
            f = re.sub(r"\d+", "N", rot)
            f = re.sub(r"\s+", " ", f).strip()[:70]
            formas[f] += 1
            exemplos.setdefault(f, rot[:100])
        leg = None
print(f"formas distintas: {len(formas)}")
for f, n in formas.most_common(40):
    print(f"  {n:>4}  {f}")
