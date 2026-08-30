"""Fase 3: que unidades existem no HTML coletado, e em que quantidade."""
import html as htmlmod
import json
import re
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

BASE = Path(__file__).parent
posts = json.loads((BASE / "bruto" / "wp" / "posts.json").read_text(encoding="utf-8"))

NUM = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s+(.*)$")
QUADRO = re.compile(
    r"(Quadro|Figura|Tabela)\s*(\d+)\s*[–—-]\s*(.+?)\s*$", re.IGNORECASE)

numeradas, sem_numero = [], []
tipos_quadro = Counter()
n_tabelas = n_linhas = 0
fontes = Counter()

for p in posts:
    t = htmlmod.unescape(re.sub(r"<[^>]+>", "", p["title"]["rendered"])).strip()
    m = NUM.match(t)
    (numeradas if m else sem_numero).append((m.group(1) if m else None, t, p["slug"]))

    soup = BeautifulSoup(p["content"]["rendered"], "lxml")
    for tab in soup.find_all("table"):
        n_tabelas += 1
        n_linhas += len(tab.find_all("tr"))
    for par in soup.find_all("p"):
        txt = par.get_text(" ", strip=True)
        mq = QUADRO.match(txt)
        if mq:
            tipos_quadro[mq.group(3)[:60]] += 1
        if txt.startswith("Fonte:"):
            fontes[txt[:70]] += 1

print(f"posts               : {len(posts)}")
print(f"secoes numeradas    : {len(numeradas)}")
print(f"sem numeracao       : {len(sem_numero)}")
for n, t, s in sem_numero:
    print(f"    - {t[:70]}  [{s}]")

print(f"\ntabelas             : {n_tabelas}")
print(f"linhas de tabela    : {n_linhas}")
print(f"legendas de quadro  : {sum(tipos_quadro.values())}")
print("\ntipos de quadro mais comuns:")
for t, n in tipos_quadro.most_common(25):
    print(f"  {n:>4}  {t}")
print("\nfontes declaradas mais comuns:")
for t, n in fontes.most_common(12):
    print(f"  {n:>4}  {t}")

niveis = Counter(len(n.split(".")) for n, _, _ in numeradas if n)
print("\nprofundidade da numeracao:", dict(sorted(niveis.items())))
