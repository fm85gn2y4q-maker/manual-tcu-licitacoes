"""Ensaio das ferramentas do servidor, direto sobre as funcoes.

Nao exercita o transporte — exercita o que o advogado vai receber. Cada teste
pergunta uma coisa que um procurador perguntaria, e confere que a resposta traz
o que precisa trazer: a pagina que se cita, a natureza do trecho, e o aviso de
regime quando o julgado for anterior a 2021.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import servidor as S  # noqa: E402

falhas = []


def checa(nome, ok, detalhe=""):
    print(("  OK   " if ok else "  FALHA") + "  " + nome +
          (("  -> " + str(detalhe)) if detalhe else ""))
    if not ok:
        falhas.append(nome)


def secao(t):
    print()
    print("=" * 72)
    print(t)
    print("=" * 72)


def main():
    secao("1. cobertura_do_acervo")
    c = S.cobertura_do_acervo()
    checa("210 secoes", c["conteudo"]["secoes"] == 210)
    checa("1161 julgados", c["jurisprudencia"]["julgados_citados"] == 1161)
    checa("declara os anteriores a 2021",
          c["jurisprudencia"]["anteriores_a_2021"] == 860,
          c["jurisprudencia"]["anteriores_a_2021"])
    checa("declara o que nao alcanca", len(c["o_que_nao_alcanca"]) >= 4)
    checa("declara a data da coleta", bool(c["coletado_em"]), c["coletado_em"])

    secao("2. pesquisar_orientacao — 'pesquisa de precos'")
    r = S.pesquisar_orientacao("pesquisa de precos", limite=5)
    checa("achou secoes", r["encontrados"] > 0, r["encontrados"])
    checa("toda secao traz pagina impressa",
          all(s["pagina_impressa"] for s in r["secoes"]))
    checa("toda secao declara a natureza como orientacao, nao decisao",
          all("NÃO é decisão" in s["natureza"] for s in r["secoes"]))
    for s in r["secoes"][:3]:
        print("     %-12s %-46s p.%-5s julgados=%d"
              % (s["secao"], s["titulo"][:46], s["pagina_impressa"],
                 s["julgados_citados_nesta_secao"]))

    secao("3. pesquisar_jurisprudencia — 'sobrepreco em obra'")
    j = S.pesquisar_jurisprudencia("sobrepreco em obra", limite=6)
    checa("achou julgados", j["encontrados"] > 0, j["encontrados"])
    checa("todo julgado tem citacao e enunciado",
          all(x["citacao"] and x["enunciado"] for x in j["julgados"]))
    antigos = [x for x in j["julgados"] if x["ano"] and x["ano"] < 2021]
    checa("todo julgado anterior a 2021 traz o aviso de regime",
          all(any("ANTES da Lei 14.133/2021" in a for a in x["avisos"])
              for x in antigos),
          "%d anteriores" % len(antigos))
    checa("todo julgado avisa que a edicao para em 2025",
          all(any("5ª edição" in a for a in x["avisos"]) for x in j["julgados"]))
    checa("o link e declarado como busca, nao como inteiro teor",
          "CONSULTAS de busca" in j["aviso"])
    checa("julgado nao vem repetido na mesma busca",
          len({(x["citacao"], x["enunciado"]) for x in j["julgados"]})
          == len(j["julgados"]))
    for x in j["julgados"][:3]:
        print("     %-38s %s" % (x["citacao"], x["enunciado"][:60]))
        print("        onde: %s" % ", ".join(
            "item %s (p.%s)" % (o["secao"], o["pagina_impressa"])
            for o in x["onde_no_manual"]))

    secao("4. filtro de regime")
    novo = S.pesquisar_jurisprudencia("sobrepreco em obra",
                                      apenas_de_2021_em_diante=True, limite=10)
    checa("filtro devolve so julgado de 2021 em diante",
          all(x["ano"] >= 2021 for x in novo["julgados"] if x["ano"]),
          "%d julgados" % novo["encontrados"])
    checa("o filtro aplicado e declarado",
          "2021 em diante" in novo["filtro_aplicado"])

    secao("5. ler_secao — 3.2, cujo corpo o PDF perdeu")
    s = S.ler_secao("3.2")
    corpo = " ".join(b["texto"] for b in s["blocos"])
    checa("traz o texto que no PDF e imagem",
          "afastando favoritismos" in corpo)
    checa("traz os quadros", len(s["quadros"]) >= 2, len(s["quadros"]))
    checa("traz as notas de rodape", len(s["notas_de_rodape"]) >= 30,
          len(s["notas_de_rodape"]))
    checa("cada quadro declara sua natureza",
          all(q["natureza"] for q in s["quadros"]))
    checa("a citacao traz a pagina impressa", "p. 149" in s["citacao"],
          s["citacao"])
    print("     citacao:", s["citacao"])
    for q in s["quadros"]:
        print("     %-52s [%s] %d linhas p.%s"
              % (q["legenda"][:52], q["categoria"], len(q["linhas"]),
                 q["pagina_impressa"]))

    secao("6. ler_secao com numero inexistente")
    e = S.ler_secao("9.9.9")
    checa("erra com clareza em vez de devolver vazio", "erro" in e)

    secao("7. riscos_de — etapa de planejamento")
    rk = S.riscos_de(secao="4.1", limite=20)
    checa("achou riscos da secao 4.1", rk["encontrados"] > 0, rk["encontrados"])
    checa("declara que risco nao e norma nem precedente",
          all("não é norma" in x["natureza"] for x in rk["linhas"]))
    checa("o cabecalho 'Riscos' nao vem como se fosse um risco",
          not any(x["texto"].strip().startswith("Riscos") and len(x["texto"]) < 20
                  for x in rk["linhas"]))
    for x in rk["linhas"][:3]:
        print("     -", x["texto"][:110])

    secao("8. referencias_normativas — 'dispensa de licitacao'")
    rn = S.referencias_normativas("dispensa de licitacao", limite=5)
    checa("achou dispositivos", rn["encontrados"] > 0, rn["encontrados"])
    checa("declara que a autoridade e da lei",
          all("autoridade é da lei" in x["natureza"] for x in rn["linhas"]))

    secao("9. julgado_no_manual — o mais citado (2622/2015)")
    a = S.julgado_no_manual("2622", 2015)
    checa("achou o acordao", a["encontrado"])
    checa("achou todas as ocorrencias", a["quantas_vezes"] >= 10,
          a["quantas_vezes"])
    checa("cada ocorrencia diz onde no manual",
          all(o["onde_no_manual"]["secao"] for o in a["ocorrencias"]))
    print("     citado %d vezes, em: %s" % (
        a["quantas_vezes"],
        ", ".join(sorted({o["onde_no_manual"]["secao"] for o in a["ocorrencias"]}))))

    secao("10. julgado_no_manual — acordao ausente")
    n = S.julgado_no_manual("99999", 2026)
    checa("nao encontrado nao vira 'o TCU nao decidiu'",
          "NÃO significa" in n["o_que_isso_significa"])

    secao("11. ler_pagina — pagina rasterizada no PDF")
    p = S.ler_pagina(149)
    checa("avisa que a pagina esta incompleta no PDF", "aviso" in p,
          "%d chars" % p["chars"])
    checa("aponta a secao provavel", p["secao_provavel"] is not None)
    print("     aviso:", p.get("aviso", "")[:140])

    secao("12. sumario")
    su = S.sumario(capitulo="4", profundidade=2)
    checa("sumario do cap.4", su["quantos"] > 0, su["quantos"])
    checa("todo item traz pagina",
          all(i["pagina_impressa"] for i in su["itens"]))

    secao("13. pontos_cegos")
    pc = S.pontos_cegos()
    checa("declara as figuras sem texto",
          pc["figuras_sem_texto"]["quantas"] == 12,
          pc["figuras_sem_texto"]["quantas"])
    checa("declara as linhas que nao sao precedente",
          pc["linhas_que_nao_sao_precedente"]["quantas"] == 150,
          pc["linhas_que_nao_sao_precedente"]["quantas"])
    checa("declara as 91 paginas rasterizadas",
          pc["paginas_rasterizadas_no_pdf"]["quantas"] == 91,
          pc["paginas_rasterizadas_no_pdf"]["quantas"])

    secao("14. search / fetch (ChatGPT)")
    sr = S.search("prorrogacao de contrato de servico continuado")
    checa("search devolve resultados", len(sr["results"]) > 0, len(sr["results"]))
    checa("todo resultado tem id, title, text, url",
          all(all(k in r for k in ("id", "title", "text", "url"))
              for r in sr["results"]))
    ft = S.fetch(sr["results"][0]["id"])
    checa("fetch devolve o conteudo", len(ft["text"]) > 100, len(ft["text"]))

    secao("15. relaxamento e busca vazia")
    v = S.pesquisar_orientacao("zzzqqq inexistente xyzw")
    checa("consulta sem acerto devolve vazio sem quebrar",
          v["encontrados"] == 0 or bool(v["relaxamento"]))
    fl = S.pesquisar_jurisprudencia("licitacao deserta fracassada")
    if fl["relaxamento"]:
        checa("relaxamento e declarado", "relaxada" in fl["relaxamento"])
        print("     relaxamento:", fl["relaxamento"][:100])
    else:
        print("     (sem relaxamento nesta consulta)")

    print()
    print("=" * 72)
    if falhas:
        print("FALHAS: %d" % len(falhas))
        for f in falhas:
            print("  -", f)
        return 1
    print("TODOS OS ENSAIOS PASSARAM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
