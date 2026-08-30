"""Fase 4: o que ha dentro dos quadros de jurisprudencia e de riscos."""
import html as htmlmod
import json
import re
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

BASE = Path(__file__).parent
posts = json.loads((BASE / "bruto" / "wp" / "posts.json").read_text(encoding="utf-8"))

LEGENDA = re.compile(r"(Quadro|Figura|Tabela)\s*(\d+)\s*[–—-]\s*(.+)$", re.I)
ACORDAO = re.compile(
    r"Acórdão\s+([\d.]+)\s*/\s*(\d{4})\s*[-–]?\s*TCU\s*[-–]?\s*"
    r"(Plenário|Primeira Câmara|Segunda Câmara|1ª Câmara|2ª Câmara)?",
    re.I)
SUMULA = re.compile(r"Súmula\s*[–-]?\s*TCU\s*(\d+)", re.I)

rotulos = Counter()
acordaos = Counter()
sumulas = Counter()
anos = Counter()
colegiados = Counter()
n_juris_linhas = 0
n_risco_linhas = 0
amostra_risco = []
sem_reconhecer = []

for p in posts:
    soup = BeautifulSoup(p["content"]["rendered"], "lxml")
    # a legenda vem num <p> imediatamente antes da <figure>/<table>
    legenda_atual = None
    for el in soup.find_all(["p", "table"]):
        if el.name == "p":
            m = LEGENDA.match(el.get_text(" ", strip=True))
            if m:
                legenda_atual = (m.group(1), int(m.group(2)), m.group(3).strip())
            continue
        if not legenda_atual:
            continue
        tipo = legenda_atual[2]
        linhas = el.find_all("tr")
        if tipo.lower().startswith("jurisprud"):
            for tr in linhas[1:]:
                tds = tr.find_all(["td", "th"])
                if len(tds) < 2:
                    continue
                n_juris_linhas += 1
                rot = tds[0].get_text(" ", strip=True)
                rotulos[rot[:60]] += 1
                ma = ACORDAO.search(rot)
                ms = SUMULA.search(rot)
                if ma:
                    acordaos[f"{ma.group(1)}/{ma.group(2)}"] += 1
                    anos[ma.group(2)] += 1
                    colegiados[(ma.group(3) or "?").title()] += 1
                elif ms:
                    sumulas[ms.group(1)] += 1
                elif rot:
                    sem_reconhecer.append(rot[:80])
        elif tipo.lower().startswith("risco"):
            for tr in linhas[1:]:
                tds = tr.find_all(["td", "th"])
                if len(tds) >= 2:
                    n_risco_linhas += 1
                    if len(amostra_risco) < 4:
                        amostra_risco.append([
                            td.get_text(" ", strip=True)[:120] for td in tds])
        legenda_atual = None

print(f"linhas em quadros de jurisprudencia : {n_juris_linhas}")
print(f"  acordaos distintos                : {len(acordaos)}")
print(f"  ocorrencias de acordao            : {sum(acordaos.values())}")
print(f"  sumulas distintas                 : {len(sumulas)}")
print(f"  ocorrencias de sumula             : {sum(sumulas.values())}")
print(f"  rotulos nao reconhecidos          : {len(sem_reconhecer)}")
print(f"\nlinhas em quadros de riscos         : {n_risco_linhas}")

print("\nanos dos acordaos:")
for a, n in sorted(anos.items()):
    print(f"  {a}: {n}")
print("\ncolegiados:", dict(colegiados))
print("\nacordaos mais citados:")
for a, n in acordaos.most_common(12):
    print(f"  {n:>3}x  Acordao {a}")
print("\nrotulos nao reconhecidos (amostra):")
for r in sem_reconhecer[:15]:
    print("  -", r)
print("\namostra de linha de risco:")
for r in amostra_risco:
    print("  |", " || ".join(r))
