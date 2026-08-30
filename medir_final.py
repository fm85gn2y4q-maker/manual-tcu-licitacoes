"""Fase 5: fecha a medicao — mapa secao->pagina do PDF e regime dos acordaos."""
import html as htmlmod
import json
import re
from collections import Counter
from pathlib import Path

import pymupdf
from bs4 import BeautifulSoup

BASE = Path(__file__).parent
posts = json.loads((BASE / "bruto" / "wp" / "posts.json").read_text(encoding="utf-8"))
pages = json.loads((BASE / "bruto" / "wp" / "pages.json").read_text(encoding="utf-8"))
doc = pymupdf.open(BASE / "bruto" / "TCU_Licitacoes_Contratos_5ed_2025.pdf")
toc = doc.get_toc(simple=True)


def limpo(s):
    return re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def chave(t):
    t = limpo(t).lower()
    t = re.sub(r"^(\d+(?:\.\d+)*)\.?\s*", r"\1 ", t)
    return re.sub(r"[^a-z0-9à-ÿ ]+", "", t)


print("PAGES (nao sao secoes):")
for p in pages:
    print(f"  id={p['id']:>5} {limpo(p['title']['rendered'])[:50]:50} [{p['slug']}]")

vazio = [p for p in posts if not limpo(p["title"]["rendered"])]
print(f"\nposts sem titulo: {len(vazio)}")
for p in vazio:
    print(f"  id={p['id']} slug={p['slug']} chars={len(p['content']['rendered'])}")
    print("  inicio:", limpo(p["content"]["rendered"])[:200])

# mapa titulo do outline -> pagina do PDF
mapa = {chave(t): pg for _, t, pg in toc}
casados = faltando = 0
for p in posts:
    t = limpo(p["title"]["rendered"])
    if not t or t == "manual":
        continue
    if chave(t) in mapa:
        casados += 1
    else:
        faltando += 1
        if faltando <= 12:
            print(f"  SEM PAR NO PDF: {t[:70]}")
print(f"\nsecoes casadas com o sumario do PDF: {casados} | sem par: {faltando}")
print(f"offset pagina PDF -> pagina impressa: 11 (conferido nas p.62 e p.160)")

# regime dos acordaos
LEG = re.compile(r"(Quadro|Figura|Tabela)\s*(\d+)\s*[–—-]\s*(.+)$", re.I)
JULG = re.compile(
    r"(Ac[oó]rd[aã]os?|Decis[aã]o|S[uú]mula)\s*"
    r"[–-]?\s*(?:TCU\s*)?(\d[\d.]*)\s*(?:/\s*(\d{4}))?", re.I)
regime = Counter()
anos_all = []
for p in posts:
    soup = BeautifulSoup(p["content"]["rendered"], "lxml")
    leg = None
    for el in soup.find_all(["p", "table"]):
        if el.name == "p":
            m = LEG.match(el.get_text(" ", strip=True))
            if m:
                leg = m.group(3).strip()
            continue
        if not leg or not leg.lower().startswith("jurisprud"):
            leg = None
            continue
        for tr in el.find_all("tr")[1:]:
            tds = tr.find_all(["td", "th"])
            if len(tds) < 2:
                continue
            rot = tds[0].get_text(" ", strip=True)
            m = JULG.search(rot)
            if m and m.group(3):
                ano = int(m.group(3))
                anos_all.append(ano)
                regime["Lei 14.133/2021 (>=2021)" if ano >= 2021
                       else "Lei 8.666/1993 (<2021)"] += 1
            elif "esquisa" in rot:
                regime["nao e julgado: Pesquisa de Jurisprudencia"] += 1
            else:
                regime["rotulo sem ano"] += 1
        leg = None

tot = sum(regime.values())
print("\nREGIME DOS JULGADOS CITADOS (o achado central):")
for k, n in regime.most_common():
    print(f"  {n:>5} ({100*n/tot:4.1f}%)  {k}")
