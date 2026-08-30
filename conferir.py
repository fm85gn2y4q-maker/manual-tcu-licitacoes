"""Confere o banco contra as fontes. Falha alto se algo nao bater.

O que se quer provar aqui nao e que o banco "parece bom" — e que o texto do
manual esta todo dentro dele, que a jurisprudencia extraida corresponde ao que
o quadro diz, e que a busca acha o que existe.
"""
import html as htmlmod
import json
import re
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).parent
BANCO = BASE / "manual_tcu.sqlite3"
CRU = BASE / "bruto" / "wp"

falhas = []


def checa(nome, ok, detalhe=""):
    print(("  OK   " if ok else "  FALHA") + "  " + nome + (
        ("  -> " + detalhe) if detalhe else ""))
    if not ok:
        falhas.append(nome)


def limpo(s):
    return re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def main():
    con = sqlite3.connect(BANCO)
    con.row_factory = sqlite3.Row
    q = lambda s, *a: con.execute(s, a).fetchall()
    um = lambda s, *a: con.execute(s, a).fetchone()[0]

    print("=" * 72)
    print("1. INTEGRIDADE ESTRUTURAL")
    print("=" * 72)
    checa("210 secoes (209 posts + o cabecalho do cap.1)",
          um("SELECT COUNT(*) FROM secao") == 210)
    # A unica secao sem prosa propria e o cabecalho do capitulo 1, onde o texto
    # do manual comeca ja em 1.1. Qualquer outra vazia e defeito de extracao.
    vazias = q("SELECT numero FROM secao WHERE chars<50")
    checa("so o cabecalho do cap.1 esta sem prosa",
          [r["numero"] for r in vazias] == ["1"],
          "vazias=%s" % [r["numero"] for r in vazias])
    checa("toda secao tem pagina impressa",
          um("SELECT COUNT(*) FROM secao WHERE pagina_impressa IS NULL") == 0)
    orfas = um("SELECT COUNT(*) FROM secao s WHERE s.numero_pai IS NOT NULL "
               "AND NOT EXISTS (SELECT 1 FROM secao p WHERE p.numero=s.numero_pai)")
    checa("hierarquia fechada (todo pai existe)", orfas == 0, "orfas=%d" % orfas)
    checa("1042 paginas do PDF", um("SELECT COUNT(*) FROM pagina") == 1042)
    checa("toda linha pertence a um quadro",
          um("SELECT COUNT(*) FROM linha l LEFT JOIN quadro qd "
             "ON qd.id=l.quadro_id WHERE qd.id IS NULL") == 0)
    checa("todo julgado aponta para linha existente",
          um("SELECT COUNT(*) FROM julgado j LEFT JOIN linha l "
             "ON l.id=j.linha_id WHERE l.id IS NULL") == 0)

    print()
    print("=" * 72)
    print("2. NADA SE PERDEU NO CAMINHO (banco x HTML de origem)")
    print("=" * 72)
    posts = json.loads((CRU / "posts.json").read_text(encoding="utf-8"))
    por_id = {p["id"]: p for p in posts}
    amostra = q("SELECT id,numero,titulo,wp_id,texto FROM secao "
                "ORDER BY chars DESC LIMIT 25")
    perdidos = []
    for s in amostra:
        origem = limpo(por_id[s["wp_id"]]["content"]["rendered"])
        # tudo que a secao guarda: prosa + quadros + notas
        guardado = s["texto"] + " " + " ".join(
            r["conteudo"] + " " + (r["rotulo"] or "")
            for r in q("SELECT l.rotulo,l.conteudo FROM linha l "
                       "JOIN quadro qd ON qd.id=l.quadro_id WHERE qd.secao_id=?",
                       s["id"])) + " " + " ".join(
            r["texto"] for r in q("SELECT texto FROM nota WHERE secao_id=?", s["id"]))
        g = set(re.findall(r"\w{6,}", guardado.lower()))
        o = set(re.findall(r"\w{6,}", origem.lower()))
        falta = o - g
        if len(falta) > len(o) * 0.02:
            perdidos.append((s["numero"], len(falta), len(o), sorted(falta)[:6]))
    checa("nas 25 maiores secoes, >=98%% do vocabulario da origem esta no banco",
          not perdidos, "; ".join("%s perde %d/%d %s" % p for p in perdidos[:3]))

    print()
    print("=" * 72)
    print("3. O CONTEUDO QUE O PDF PERDEU ESTA AQUI")
    print("=" * 72)
    # p.149 impressa: principios do art. 5o, que no PDF sao imagem
    pdf149 = um("SELECT texto FROM pagina WHERE pagina_impressa=149")
    checa("no PDF a p.149 nao tem 'impessoalidade' (esta em imagem)",
          "impessoalidade" not in pdf149.lower(),
          "chars da pagina no PDF=%d" % len(pdf149))
    achou = um("SELECT COUNT(*) FROM secao WHERE numero='3.2' "
               "AND texto LIKE '%afastando favoritismos%'")
    checa("o banco tem o texto do principio da impessoalidade", achou == 1)
    checa("secao 3.2 traz os 8+ principios do art. 5o",
          um("SELECT COUNT(*) FROM bloco b JOIN secao s ON s.id=b.secao_id "
             "WHERE s.numero='3.2' AND b.tipo='item'") >= 8)

    print()
    print("=" * 72)
    print("4. JURISPRUDENCIA: O QUE FOI EXTRAIDO CORRESPONDE AO QUADRO")
    print("=" * 72)
    n_lin_juris = um("SELECT COUNT(*) FROM linha l JOIN quadro qd "
                     "ON qd.id=l.quadro_id WHERE qd.categoria='jurisprudencia' "
                     "AND l.ordem>1")
    n_pesq = um("SELECT COUNT(*) FROM linha l JOIN quadro qd ON qd.id=l.quadro_id "
                "WHERE qd.categoria='jurisprudencia' AND l.ordem>1 "
                "AND l.rotulo LIKE '%esquisa de %urisprud%'")
    n_com = um("SELECT COUNT(DISTINCT linha_id) FROM julgado")
    print("  linhas de quadro de jurisprudencia : %d" % n_lin_juris)
    print("    viraram julgado                  : %d" % n_com)
    print("    'Pesquisa de Jurisprudencia'     : %d  (nao e precedente)" % n_pesq)
    print("    restantes sem julgado            : %d" % (n_lin_juris - n_com - n_pesq))
    checa("no maximo 3 linhas de jurisprudencia sem classificacao",
          n_lin_juris - n_com - n_pesq <= 3)
    checa("todo julgado tem enunciado", um(
        "SELECT COUNT(*) FROM julgado WHERE LENGTH(enunciado)<20") == 0)
    checa("nenhum julgado com ano fora de 1990..2026", um(
        "SELECT COUNT(*) FROM julgado WHERE ano IS NOT NULL "
        "AND (ano<1990 OR ano>2026)") == 0)
    checa("nenhuma 'Pesquisa de Jurisprudencia' virou julgado", um(
        "SELECT COUNT(*) FROM julgado WHERE rotulo_original "
        "LIKE '%esquisa de %urisprud%'") == 0)

    print()
    print("=" * 72)
    print("5. A BUSCA ACHA O QUE EXISTE")
    print("=" * 72)
    for termo, onde in [("sobrepreco", "fts_secao"), ("licitacao", "fts_secao"),
                        ("superfaturamento", "fts_julgado"),
                        ("inexigibilidade", "fts_julgado"),
                        ("pesquisa de precos", "fts_linha")]:
        n = um("SELECT COUNT(*) FROM %s WHERE %s MATCH ?" % (onde, onde),
               '"%s"' % termo)
        checa("%s acha \"%s\"" % (onde, termo), n > 0, "%d acertos" % n)
    # o tokenizer tem de ignorar acento
    a = um("SELECT COUNT(*) FROM fts_secao WHERE fts_secao MATCH ?", '"licitacao"')
    b = um("SELECT COUNT(*) FROM fts_secao WHERE fts_secao MATCH ?", '"licitação"')
    checa("busca ignora acento (licitacao == licitacao)", a == b, "%d vs %d" % (a, b))

    print()
    print("=" * 72)
    print("6. O ACHADO CENTRAL, MEDIDO")
    print("=" * 72)
    tot = um("SELECT COUNT(*) FROM julgado")
    ant = um("SELECT COUNT(*) FROM julgado WHERE anterior_a_14133=1")
    pos = um("SELECT COUNT(*) FROM julgado WHERE anterior_a_14133=0")
    print("  julgados citados no manual        : %d" % tot)
    print("    julgados ANTES de 01/04/2021    : %d (%.1f%%)" % (ant, 100*ant/tot))
    print("    julgados de 2021 em diante      : %d (%.1f%%)" % (pos, 100*pos/tot))
    print("  acordaos distintos                : %d" % um(
        "SELECT COUNT(DISTINCT numero||'/'||COALESCE(ano,0)) FROM julgado "
        "WHERE especie='acordao'"))
    print("  sumulas distintas                 : %d" % um(
        "SELECT COUNT(DISTINCT numero) FROM julgado WHERE especie='sumula'"))
    print("  faixa de anos                     : %s a %s" % (
        um("SELECT MIN(ano) FROM julgado WHERE ano IS NOT NULL"),
        um("SELECT MAX(ano) FROM julgado WHERE ano IS NOT NULL")))
    print()
    print("  quadros por categoria:")
    for r in q("SELECT categoria,COUNT(*) n,SUM(n_linhas) l FROM quadro "
               "GROUP BY categoria ORDER BY n DESC"):
        print("    %-24s %4d quadros, %5d linhas" % (r[0], r[1], r[2] or 0))

    print()
    print("=" * 72)
    if falhas:
        print("FALHAS: %d" % len(falhas))
        for f in falhas:
            print("  -", f)
        return 1
    print("TODAS AS CONFERENCIAS PASSARAM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
