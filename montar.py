"""Monta o banco do manual a partir das DUAS fontes, que se completam.

HTML da versao interativa (211 posts do WordPress do TCU): e o texto de
registro. No PDF publicado, ~160 paginas tiveram o corpo colado no Word como
IMAGEM — a p.149 impressa, com os principios do art. 5o da Lei 14.133/2021,
nao tem uma letra de texto. O HTML traz esse mesmo conteudo em texto nativo,
com as notas de rodape e os quadros em tabela.

PDF (1.042 paginas): entra por tres coisas que o HTML nao tem — a pagina
impressa que se cita, a Lista de quadros com a pagina de cada quadro, e as
Referencias bibliograficas.

Descartado de proposito: o post `137-2` (id 137), duplicata desatualizada de
`3-3-agentes-publicos` (id 195). Fica registrado em nota_de_coleta.
"""
import hashlib
import html as htmlmod
import json
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pymupdf
from bs4 import BeautifulSoup

BASE = Path(__file__).parent
CRU = BASE / "bruto" / "wp"
PDF = BASE / "bruto" / "TCU_Licitacoes_Contratos_5ed_2025.pdf"
BANCO = BASE / "manual_tcu.sqlite3"
OFFSET = 11  # pagina_impressa = pagina_pdf - 11 (conferido nas p.62 e p.160)

URL_SITE = "https://licitacoesecontratos.tcu.gov.br/"
URL_PDF = ("https://licitacoesecontratos.tcu.gov.br/wp-content/uploads/sites/11/"
           "2024/09/Licitacoes-e-Contratos-Orientacoes-e-Jurisprudencia-do-TCU-"
           "5a-Edicao-v4.pdf")

DESCARTAR_SLUG = {"137-2"}          # duplicata
NAO_SECAO_SLUG = {"manual"}         # o proprio sumario

LEGENDA = re.compile(r"^(Quadro|Figura|Tabela)\s*(\d+)\s*[–—-]\s*(.+?)\s*$", re.I)
NUMERO = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s+(.*)$")
FTN = re.compile(r"^_ftn(\d+)$")

# A gramatica abaixo saiu de levantar as 48 formas que de fato ocorrem no
# corpus, inclusive os erros do proprio TCU: "Plenario", "Plenari o",
# "AcordaoN/N" sem espaco e "Acordao N.NNN/AAAA" com separador de milhar.
JULGADO = re.compile(
    r"(?P<especie>Acórdãos?|Acordaos?|Decisões|Decisão|"
    r"Súmula|Sumula)"
    r"\s*[–—-]?\s*(?:TCU\s*[–—-]?\s*)?"
    # ate 5 digitos: nas Camaras a numeracao passa de 10.000
    # (Acordao 18587/2021-TCU-Primeira Camara)
    r"(?P<num>\d{1,5}(?:\.\d{3})*)"
    r"(?:\s*/\s*(?P<ano>\d{4}))?"
    r"\s*[–—-]?\s*(?:TCU)?\s*[–—-]?\s*"
    # "Camera" e erro do proprio manual, numa linha do quadro 269
    r"(?P<col>Plenári\s*[oó]|Plenari\s*[oó]|"
    r"Primeira\s+Câm[ae]ra|Segunda\s+Câm[ae]ra|"
    r"1[ªa]\s*Câm[ae]ra|2[ªa]\s*Câm[ae]ra)?",
    re.I)
LISTA_ACORDAOS = re.compile(
    r"Acórdãos\s+((?:\d[\d.]*\s*,\s*)+\d[\d.]*)"
    r"[^0-9]{0,40}?(?:ano\s+de\s+)?(\d{4})", re.I)
PESQUISA = re.compile(r"pesquisa\s+de\s+jurisprud", re.I)

CATEGORIAS = (
    ("jurisprud", "jurisprudencia"),
    ("risco", "riscos"),
    ("modelo", "modelos"),
    ("refer", "referencias_normativas"),
)


def limpo(s):
    return re.sub(r"\s+", " ", htmlmod.unescape(s)).strip()


def texto_de(el):
    return limpo(el.get_text(" ", strip=True))


def chave_titulo(t):
    t = limpo(t).lower()
    t = re.sub(r"^(\d+(?:\.\d+)*)\.?\s*", r"\1 ", t)
    return re.sub(r"[^a-z0-9à-ÿ ]+", "", t)


def categoria_de(titulo):
    t = titulo.lower()
    for pref, cat in CATEGORIAS:
        if t.startswith(pref):
            return cat
    return "outro"


def normaliza_colegiado(c):
    if not c:
        return None
    c = re.sub(r"\s+", " ", c).strip().lower()
    if c.startswith("plen"):
        return "Plenário"
    if c.startswith("primeira") or c.startswith("1"):
        return "Primeira Câmara"
    if c.startswith("segunda") or c.startswith("2"):
        return "Segunda Câmara"
    return None


def especie_de(e):
    e = e.lower()
    if e.startswith("s"):
        return "sumula"
    if e.startswith("d"):
        return "decisao"
    return "acordao"


def cita(especie, numero, ano, colegiado):
    nome = {"acordao": "Acórdão", "sumula": "Súmula TCU",
            "decisao": "Decisão"}[especie]
    if especie == "sumula":
        return nome + " " + numero
    base = nome + " " + numero
    if ano:
        base += "/" + str(ano)
    base += "-TCU"
    if colegiado:
        base += "-" + colegiado
    return base


def sha256(p):
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def parse_secao(soup):
    """Percorre o HTML na ordem e devolve (blocos, quadros, notas)."""
    blocos, quadros, notas = [], [], []
    pendente = None   # legenda aguardando a tabela/figura
    corpo = soup.body or soup
    for el in corpo.find_all(
            ["p", "ol", "ul", "figure", "table", "h1", "h2", "h3", "h4"],
            recursive=True):
        # nao reprocessar o que ja esta dentro de uma figure/table
        if el.find_parent(["figure", "table"]) is not None:
            continue

        if el.name in ("h1", "h2", "h3", "h4"):
            t = texto_de(el)
            if t:
                blocos.append(("subtitulo", t))
            continue

        if el.name == "p":
            t = texto_de(el)
            if not t:
                continue
            a = el.find("a", id=FTN)
            if a is not None:
                m = FTN.match(a.get("id", ""))
                corpo_nota = re.sub(r"^\[\d+\]\s*", "", limpo(t))
                notas.append((int(m.group(1)), corpo_nota))
                continue
            m = LEGENDA.match(t)
            if m:
                pendente = {"especie": m.group(1).title(),
                            "numero": int(m.group(2)),
                            "titulo": m.group(3),
                            "linhas": [], "fonte": None, "so_imagem": 0}
                continue
            if t.lower().startswith("fonte:") and quadros:
                quadros[-1]["fonte"] = t
                continue
            blocos.append(("prosa", t))
            continue

        if el.name in ("ol", "ul"):
            for li in el.find_all("li", recursive=False):
                t = texto_de(li)
                if t:
                    blocos.append(("item", t))
            continue

        # figure / table
        tab = el if el.name == "table" else el.find("table")
        if tab is None:
            if pendente is not None:
                pendente["so_imagem"] = 1
                quadros.append(pendente)
                pendente = None
            continue

        linhas = []
        for tr in tab.find_all("tr"):
            cels = tr.find_all(["td", "th"])
            if not cels:
                continue
            vals = [texto_de(c) for c in cels]
            if not any(vals):
                continue
            link = None
            a = cels[0].find("a", href=True)
            if a is not None:
                link = a["href"]
            linhas.append({"colunas": vals, "url": link})

        if pendente is None:
            pendente = {"especie": "Tabela", "numero": None,
                        "titulo": "(sem legenda)", "linhas": [],
                        "fonte": None, "so_imagem": 0}
        pendente["linhas"] = linhas
        quadros.append(pendente)
        pendente = None

    if pendente is not None:
        pendente["so_imagem"] = 1
        quadros.append(pendente)
    return blocos, quadros, notas


def julgados_da_linha(rotulo):
    """Devolve a lista de julgados que o rotulo declara. [] se nao houver.

    Linha 'Pesquisa de Jurisprudencia' devolve [] de proposito: e uma sugestao
    de busca no portal do TCU, nao um precedente.
    """
    if not rotulo or PESQUISA.search(rotulo):
        return []
    # "Acordaos 2340, 2341, ..., todos do ano de 2015"
    ml = LISTA_ACORDAOS.search(rotulo)
    if ml:
        ano = int(ml.group(2))
        mj = JULGADO.search(rotulo)
        col = normaliza_colegiado(mj.group("col") if mj else None)
        return [("acordao", n.replace(".", ""), ano, col)
                for n in re.findall(r"\d[\d.]*", ml.group(1))]
    out = []
    for m in JULGADO.finditer(rotulo):
        esp = especie_de(m.group("especie"))
        num = m.group("num").replace(".", "")
        ano = int(m.group("ano")) if m.group("ano") else None
        if esp != "sumula" and ano is None:
            continue          # "Acordao 1234" sem ano nao identifica julgado
        out.append((esp, num, ano, normaliza_colegiado(m.group("col"))))
    return out


def main():
    if BANCO.exists():
        BANCO.unlink()
    for suf in ("-wal", "-shm"):
        p = Path(str(BANCO) + suf)
        if p.exists():
            p.unlink()

    con = sqlite3.connect(BANCO)
    con.executescript((BASE / "esquema.sql").read_text(encoding="utf-8"))

    posts = json.loads((CRU / "posts.json").read_text(encoding="utf-8"))
    doc = pymupdf.open(PDF)
    toc = doc.get_toc(simple=True)
    mapa_pag = {chave_titulo(t): pg for _, t, pg in toc}

    con.execute(
        "INSERT INTO obra (id,titulo,edicao,ano,orgao,url_site,url_pdf,"
        "sha256_pdf,paginas_pdf,offset_pagina,coletado_em) "
        "VALUES (1,?,?,?,?,?,?,?,?,?,?)",
        ("Licitações & Contratos: Orientações e "
         "Jurisprudência do TCU",
         "5ª edição", 2025, "Tribunal de Contas da União",
         URL_SITE, URL_PDF, sha256(PDF), doc.page_count, OFFSET,
         date.today().isoformat()))

    # ---- secoes, blocos, quadros, linhas, julgados, notas -------------------
    secoes = []
    for p in posts:
        if p["slug"] in DESCARTAR_SLUG or p["slug"] in NAO_SECAO_SLUG:
            continue
        t = limpo(re.sub(r"<[^>]+>", "", p["title"]["rendered"]))
        m = NUMERO.match(t)
        if not m:
            continue
        secoes.append((m.group(1), m.group(2).strip(), p))
    secoes.sort(key=lambda x: [int(n) for n in x[0].split(".")])

    # O capitulo 1 nao tem post proprio: no manual ele e so o cabecalho, e a
    # prosa comeca ja em 1.1. Os capitulos 2 a 6 tem prosa propria. Entra aqui
    # como cabecalho declarado, para a hierarquia fechar sem inventar texto.
    CAP1 = {"id": None, "slug": "1-introducao", "modified": None,
            "link": URL_SITE + "1-1-objetivo-e-escopo/",
            "title": {"rendered": "1. INTRODUÇÃO"},
            "content": {"rendered": ""}}
    secoes.insert(0, ("1", "Introdução", CAP1))

    stats = {"blocos": 0, "quadros": 0, "linhas": 0, "julgados": 0,
             "notas": 0, "pesquisa": 0, "sem_julgado": 0, "quadros_imagem": 0}
    rotulos_sem_julgado = []

    for ordem, (numero, titulo, p) in enumerate(secoes, 1):
        partes = numero.split(".")
        pai = ".".join(partes[:-1]) if len(partes) > 1 else None
        pdf_pag = mapa_pag.get(chave_titulo(numero + ". " + titulo))
        soup = BeautifulSoup(p["content"]["rendered"], "lxml")
        blocos, quadros, notas = parse_secao(soup)
        texto = "\n\n".join(t for _, t in blocos)

        cur = con.execute(
            "INSERT INTO secao (numero,titulo,nivel,numero_pai,capitulo,slug,"
            "url,ordem,pagina_pdf,pagina_impressa,wp_id,wp_modified,texto,chars)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (numero, titulo, len(partes), pai, partes[0], p["slug"], p["link"],
             ordem, pdf_pag, (pdf_pag - OFFSET) if pdf_pag else None,
             p["id"], p["modified"], texto, len(texto)))
        sid = cur.lastrowid

        con.executemany(
            "INSERT INTO bloco (secao_id,ordem,tipo,texto) VALUES (?,?,?,?)",
            [(sid, i, tp, tx) for i, (tp, tx) in enumerate(blocos, 1)])
        stats["blocos"] += len(blocos)

        con.executemany(
            "INSERT INTO nota (secao_id,numero,texto) VALUES (?,?,?)",
            [(sid, n, tx) for n, tx in notas])
        stats["notas"] += len(notas)

        for qo, q in enumerate(quadros, 1):
            cat = "figura" if q["so_imagem"] else categoria_de(q["titulo"])
            cq = con.execute(
                "INSERT INTO quadro (secao_id,especie,numero,titulo,categoria,"
                "fonte,ordem,n_linhas,so_imagem) VALUES (?,?,?,?,?,?,?,?,?)",
                (sid, q["especie"], q["numero"], q["titulo"], cat, q["fonte"],
                 qo, max(0, len(q["linhas"]) - 1), q["so_imagem"]))
            qid = cq.lastrowid
            stats["quadros"] += 1
            stats["quadros_imagem"] += q["so_imagem"]

            for lo, ln in enumerate(q["linhas"], 1):
                cols = ln["colunas"]
                rot = cols[0] if cols else ""
                cont = " | ".join(cols[1:]) if len(cols) > 1 else rot
                # Cabecalho: a 1a linha, quando tem mais de uma coluna ou e
                # curta. As duas excecoes medidas sao quadros de jurisprudencia
                # de coluna unica que abrem com uma frase inteira — conteudo.
                cab = 1 if lo == 1 and (len(cols) > 1 or len(cont) < 40) else 0
                cl = con.execute(
                    "INSERT INTO linha (quadro_id,ordem,rotulo,conteudo,"
                    "url_rotulo,n_colunas,colunas_json,cabecalho) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (qid, lo, rot, cont, ln["url"], len(cols),
                     json.dumps(cols, ensure_ascii=False), cab))
                lid = cl.lastrowid
                stats["linhas"] += 1

                if cat != "jurisprudencia" or cab:
                    continue
                if PESQUISA.search(rot or ""):
                    stats["pesquisa"] += 1
                    continue
                js = julgados_da_linha(rot)
                if not js:
                    if rot:
                        stats["sem_julgado"] += 1
                        rotulos_sem_julgado.append(rot[:90])
                    continue
                for esp, num, ano, col in js:
                    con.execute(
                        "INSERT INTO julgado (linha_id,secao_id,especie,numero,"
                        "ano,colegiado,citacao,rotulo_original,enunciado,url,"
                        "anterior_a_14133) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (lid, sid, esp, num, ano, col,
                         cita(esp, num, ano, col), rot, cont, ln["url"],
                         (1 if ano < 2021 else 0) if ano else None))
                    stats["julgados"] += 1

    # ---- camada do PDF ------------------------------------------------------
    imgs = {r["p"]: r["area_img_pct"]
            for r in json.loads(
                (BASE / "medicao" / "imagens.json").read_text(encoding="utf-8"))}
    for i, page in enumerate(doc, 1):
        txt = page.get_text("text").strip()
        area = imgs.get(i, 0.0)
        raster = 1 if (area >= 8 and len(txt) < 1500) or len(txt) < 200 else 0
        con.execute(
            "INSERT INTO pagina (pagina_pdf,pagina_impressa,texto,chars,"
            "area_imagem_pct,rasterizada) VALUES (?,?,?,?,?,?)",
            (i, i - OFFSET if i > OFFSET else None, txt, len(txt), area, raster))

    # ---- pagina de cada quadro, pela Lista de quadros do PDF ----------------
    lista = "\n".join(doc[n - 1].get_text("text") for n in range(1022, 1034))
    lista = re.sub(r"\.{2,}", " ", lista)
    casados = 0
    for m in re.finditer(
            r"(Quadro|Figura)\s+(\d+)\s*[-–]\s*(.+?)\s+(\d{1,4})\s*$",
            lista, re.M):
        n = con.execute(
            "UPDATE quadro SET pagina_impressa=? WHERE especie=? AND numero=?",
            (int(m.group(4)), m.group(1).title(), int(m.group(2)))).rowcount
        casados += 1 if n else 0

    # ---- referencias bibliograficas (so no PDF) -----------------------------
    bib = "\n".join(doc[n - 1].get_text("text") for n in range(1034, 1043))
    bib = bib.split("Referências bibliográficas", 1)[-1]
    partes_bib = re.split(r"\n(?=[A-ZÀ-Ý]{2,}[.,]|[A-Z]\w+, [A-Z])", bib)
    linhas_bib = [re.sub(r"\s+", " ", b).strip() for b in partes_bib]
    linhas_bib = [b for b in linhas_bib if len(b) > 40]
    con.executemany("INSERT INTO referencia (ordem,texto) VALUES (?,?)",
                    list(enumerate(linhas_bib, 1)))

    con.executemany(
        "INSERT INTO nota_de_coleta (chave,valor) VALUES (?,?)",
        [("fonte_texto",
          "versao interativa (WordPress do TCU), 211 posts, API REST publica"),
         ("fonte_pagina",
          "PDF da 5a edicao, 1042 paginas, offset 11 para a pagina impressa"),
         ("descartado",
          "post 137-2 (id 137): duplicata desatualizada de 3-3-agentes-publicos "
          "(id 195), 2 chars menor e modificada em 2024-06-05 contra 2024-08-05"),
         ("capitulo_1",
          "'1. INTRODUCAO' e a unica secao sem prosa propria: no manual ela e "
          "so o cabecalho, e o texto comeca em 1.1. Entrou como cabecalho, com "
          "chars=0, para a hierarquia fechar sem inventar texto"),
         ("rasterizacao_pdf",
          "no PDF publicado o corpo de ~160 paginas foi colado como imagem; "
          "por isso o texto de registro e o do HTML, nao o do PDF"),
         ("quadros_com_pagina", str(casados))])

    con.executescript(
        "INSERT INTO fts_secao(rowid,titulo,texto) "
        "  SELECT id,titulo,texto FROM secao;"
        "INSERT INTO fts_julgado(rowid,citacao,enunciado) "
        "  SELECT id,citacao,enunciado FROM julgado;"
        "INSERT INTO fts_linha(rowid,rotulo,conteudo) "
        "  SELECT id,COALESCE(rotulo,''),conteudo FROM linha "
        "  WHERE cabecalho = 0;"
        "INSERT INTO fts_pagina(rowid,texto) SELECT pagina_pdf,texto FROM pagina;")
    con.commit()
    con.executescript("PRAGMA wal_checkpoint(TRUNCATE); VACUUM; ANALYZE;")
    con.commit()

    print("banco: %s  %.1f MB" % (BANCO.name, BANCO.stat().st_size / 1e6))
    for t in ("secao", "bloco", "quadro", "linha", "julgado", "nota",
              "pagina", "referencia"):
        n = con.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
        print("  %-12s %7d" % (t, n))
    print("\nquadros que ganharam pagina impressa: %d" % casados)
    print("linhas 'Pesquisa de Jurisprudencia' (nao viraram julgado): %d"
          % stats["pesquisa"])
    print("rotulos de jurisprudencia sem julgado reconhecido: %d"
          % stats["sem_julgado"])
    for r in rotulos_sem_julgado[:15]:
        print("   -", r)
    print("quadros que sao so imagem: %d" % stats["quadros_imagem"])
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
