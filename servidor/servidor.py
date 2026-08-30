"""Servidor MCP do manual "Licitações & Contratos" do TCU, 5a edicao.

    .venv/Scripts/python.exe servidor/servidor.py          # stdio (Claude)
    .venv/Scripts/python.exe servidor/servidor.py http     # streamable-http (ChatGPT)
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path
from urllib.parse import quote

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

# Onde o servidor procura o banco, em ordem: variavel de ambiente (o .mcpb e o
# conteiner apontam para dentro deles), ~/acervos (o disco rapido), dados/ (o
# repositorio, para quem acabou de montar).
ACERVOS = Path.home() / "acervos"


def _banco(nome: str, variavel: str) -> Path:
    do_ambiente = os.environ.get(variavel)
    if do_ambiente:
        return Path(do_ambiente)
    rapido = ACERVOS / nome
    if rapido.exists():
        return rapido
    return Path(__file__).resolve().parent.parent / "dados" / nome


BANCO = _banco("manual_tcu.sqlite3", "MANUAL_BANCO")

# A Lei 14.133/2021 foi publicada em 01/04/2021 e nesse dia entrou em vigor.
# O ano do julgado e o unico dado que o manual oferece sobre a data; por isso
# o corte e por ano, e o aviso diz "julgado em", nunca "aplicou a lei X".
ANO_NLLC = 2021

INSTRUCOES = """
Manual "Licitações & Contratos: Orientações e Jurisprudência do TCU", 5ª edição
(Tribunal de Contas da União, 2025), na íntegra: 210 seções, 484 quadros,
1.161 julgados citados e 1.513 notas de rodapé.

Como responder ao advogado:
- Entregue a orientação e o precedente, não o funcionamento da ferramenta. Não
  cite nomes de tools, identificadores internos nem estrutura de URL.
- Cite no formato do campo `citacao` — é a referência que vai para a peça, e
  ela traz a página impressa do manual.
- Chame `cobertura_do_acervo` quando precisar do alcance da base, e declare os
  limites que afetarem a resposta.

A REGRA QUE NÃO PODE SER QUEBRADA: O MANUAL NÃO É O TRIBUNAL

Num acervo de jurisprudência o risco é a proveniência; num de legislação, a
vigência. Aqui são **dois**, e os dois produzem resposta impecável e errada.

**Primeiro: o que você achou pode não ser decisão do TCU.** A mesma seção do
manual reúne, com o mesmo peso visual, cinco coisas de autoridade diferente:

    orientação          a prosa do manual — texto didático da Secretaria-Geral
                        da Presidência. NÃO é decisão, não vincula, e citá-la
                        como "o TCU decidiu" inverte o que ela é.
    jurisprudência      o enunciado de um acórdão ou súmula. É o que o Tribunal
                        de fato firmou, e é isto que se cita numa peça.
    referência normativa  texto de lei transcrito. A autoridade é da lei.
    risco               elaboração própria do manual sobre o que pode dar
                        errado. Não é norma nem precedente.
    modelo              minuta ou checklist sugerido. Não é norma.

Todo resultado traz `natureza` dizendo qual das cinco é. **Leia antes de
atribuir a frase a alguém.** E há uma armadilha específica: 150 linhas dos
quadros de jurisprudência não são julgado nenhum — dizem "Pesquisa de
Jurisprudência" e são uma sugestão de busca no portal do TCU. Elas nunca
aparecem como julgado neste acervo, de propósito.

**Segundo: 74% dos julgados citados são anteriores à Lei 14.133/2021.**
Medido nesta base: dos 1.161 julgados, 860 foram julgados antes de 2021 — sob
a Lei 8.666/1993 — contra 269 de 2021 em diante. O manual os traz porque
entende que a tese sobrevive à mudança de lei, mas **essa é uma opinião do
manual, não um fato**, e nada no enunciado avisa sob qual lei ele foi firmado.

Por isso todo julgado anterior a 2021 vem com aviso. Repasse-o. Escrever "o TCU
já decidiu que X, sob a Lei 14.133/2021" a partir de um acórdão de 2015 é o
erro mais fácil de cometer aqui e o mais difícil de perceber depois.

O QUE O LINK É, E O QUE ELE NÃO É

Nenhum dos 1.161 julgados tem link para o inteiro teor. O que o manual publica,
e o que este acervo devolve, é uma **consulta de busca** no portal do TCU —
`url_busca_no_tcu`. Ela costuma cair no acórdão, e pode não cair.

Apresente como "[Buscar no portal do TCU](url)". Nunca como "[Inteiro teor]":
a segunda forma promete um documento que o link não garante. E a tese decisiva
para uma peça se confere no inteiro teor, no portal, antes de citar.

O QUE ESTE ACERVO NÃO É

- **Não é a jurisprudência do TCU.** É o que a 5ª edição do manual selecionou:
  1.161 citações, 835 acórdãos distintos, de 1996 a 2025. O Tribunal julga
  milhares por ano. A ausência de uma tese aqui NÃO prova que o TCU não a firmou
  — prova que o manual não a trouxe.
- **Não alcança nada depois da edição.** O corte é 2025. Acórdão posterior que
  tenha mudado o entendimento não está aqui, e o enunciado não avisa que
  envelheceu.
- **Não é a lei.** Os quadros de referências normativas transcrevem dispositivos
  na redação da data da edição. Alteração posterior da Lei 14.133/2021 não se
  reflete aqui.
- **É a 5ª edição.** Se o TCU publicar a 6ª, esta base continua respondendo
  pela 5ª até ser recoletada. `cobertura_do_acervo` diz a data da coleta.

AS QUATRO BUSCAS, PROPOSITALMENTE SEPARADAS

`pesquisar_orientacao`      na prosa do manual — o que o TCU ensina a fazer.
`pesquisar_jurisprudencia`  nos enunciados — o que o Tribunal decidiu.
`riscos_de`                 nos 115 quadros de riscos — o que costuma dar errado.
`referencias_normativas`    nos 158 quadros de dispositivos legais.

Não achando na prosa, procure no enunciado antes de concluir que o manual não
tratou do assunto — e vice-versa. Prosa vazia não é manual vazio.

A busca é literal e o vocabulário jurídico não é. Quando o resultado trouxer
`relaxamento`, nenhum documento continha todos os termos e a busca foi
afrouxada: os primeiros resultados podem tratar de instituto diverso que apenas
compartilha vocabulário. Confira antes de apresentar.
""".strip()

_LOCAIS = ["127.0.0.1", "127.0.0.1:*", "localhost", "localhost:*"]


def _dominios() -> list[str]:
    return [d.strip() for d in os.environ.get("MANUAL_DOMINIOS", "").split(",")
            if d.strip()]


def _seguranca(dominios: list[str]) -> TransportSecuritySettings:
    """Politica de Host/Origin aceitos.

    O SDK bloqueia por padrao qualquer Host que nao seja local — protecao contra
    DNS rebinding. Servir por endereco publico exige declarar o dominio aqui, e
    **nao ha curinga**: a comparacao e exata. Sem isto, a hospedagem responde
    421 a tudo que vem de fora, sem dizer por que.
    """
    hosts = list(_LOCAIS)
    origens = [f"http://{h}" for h in _LOCAIS if "*" not in h]
    for dominio in dominios:
        limpo = dominio.removeprefix("https://").removeprefix("http://").rstrip("/")
        if limpo:
            hosts += [limpo, f"{limpo}:*"]
            origens.append(f"https://{limpo}")
    if dominios:
        origens += ["https://chatgpt.com", "https://chat.openai.com"]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts, allowed_origins=origens)


def _autenticacao() -> dict:
    """O ChatGPT recusa servidor MCP sem OAuth; o Claude conecta sem."""
    url = os.environ.get("MANUAL_URL_PUBLICA", "").strip()
    if not url:
        return {}
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    from autenticacao import montar
    provedor, definicoes = montar(url, os.environ.get("MANUAL_SEGREDO_OAUTH"))
    return {"auth_server_provider": provedor, "auth": definicoes}


mcp = FastMCP(
    "manual-tcu-licitacoes",
    instructions=INSTRUCOES,
    host=os.environ.get("MANUAL_HOST", "127.0.0.1"),
    port=int(os.environ.get("PORT", "8766")),
    transport_security=_seguranca(_dominios()),
    **_autenticacao(),
)

_con: sqlite3.Connection | None = None


def con() -> sqlite3.Connection:
    global _con
    if _con is None:
        if not BANCO.exists():
            raise RuntimeError(f"banco ausente: {BANCO} — rode montar.py")
        _con = sqlite3.connect(f"file:{BANCO}?mode=ro", uri=True,
                               check_same_thread=False)
        _con.row_factory = sqlite3.Row
    return _con


# ---------------------------------------------------------------------------
# Construcao da consulta: identica em espirito a dos acervos anteriores.

OPERADORES = re.compile(r'"|\bAND\b|\bOR\b|\bNOT\b|\bNEAR\b|\*|\(')

VAZIAS = {"a", "o", "as", "os", "um", "uma", "de", "do", "da", "dos", "das",
          "e", "ou", "em", "no", "na", "nos", "nas", "por", "para", "com",
          "que", "qual", "quais", "sobre", "ao", "aos", "se", "sao", "é", "eh",
          "quando", "como", "onde", "pode", "posso", "existe", "há", "ha"}

PLURAIS = ("coes", "aveis", "eis", "ais", "ois", "oes", "ns", "es", "s")


def _radical(termo: str) -> str:
    """Prefixo que aguenta a flexao do portugues.

    O FTS5 nao tem stemmer para portugues, e a busca literal falha na flexao.
    Ninguem escreve a pergunta no numero em que o TCU redigiu o enunciado.
    """
    base = "".join(c for c in unicodedata.normalize("NFD", termo.lower())
                   if unicodedata.category(c) != "Mn")
    if len(base) < 5:
        return base
    for suf in PLURAIS:
        if base.endswith(suf) and len(base) - len(suf) >= 4:
            base = base[: -len(suf)]
            break
    return base[: max(4, len(base) - 1)]


def _termos(consulta: str) -> list[str]:
    termos = [t for t in re.findall(r"[0-9A-Za-zÀ-ÿ]+", consulta)
              if len(t) > 2 and t.lower() not in VAZIAS]
    return termos or re.findall(r"[0-9A-Za-zÀ-ÿ]+", consulta)


def _expressoes(consulta: str) -> list[tuple[str, str]]:
    """As tentativas, da mais estrita para a mais frouxa. Nunca em silencio."""
    if OPERADORES.search(consulta):
        return [(consulta, "")]
    termos = _termos(consulta)
    if not termos:
        return [('""', "")]
    exata = " ".join(f'"{t}"' for t in termos)
    radicais = [f'"{_radical(t)}"*' for t in termos]
    tentativas = [(exata, "")]
    if " ".join(radicais) != exata:
        tentativas.append((" ".join(radicais),
                           "termos reduzidos ao radical, para alcançar a flexão"))
    if len(termos) > 1:
        tentativas.append((" OR ".join(radicais),
                           "NENHUM resultado exigia todos os termos: a busca foi "
                           "relaxada para QUALQUER um deles. Os primeiros "
                           "resultados podem tratar de instituto diverso que "
                           "compartilha vocabulário — confira antes de "
                           "apresentar como resposta."))
    return tentativas


def _buscar(sql: str, consulta: str, args_extra: list, limite: int):
    for expressao, relaxamento in _expressoes(consulta):
        linhas = con().execute(
            sql, [expressao] + args_extra + [min(limite, 40)]).fetchall()
        if linhas:
            return linhas, expressao, relaxamento
    return [], _expressoes(consulta)[0][0], ""


# ---------------------------------------------------------------------------
# Citacao e avisos.

NATUREZA = {
    "jurisprudencia": ("enunciado de julgado do TCU — é o que o Tribunal "
                       "firmou, e é isto que se cita"),
    "referencias_normativas": ("texto de lei transcrito pelo manual — a "
                               "autoridade é da lei, não do TCU"),
    "riscos": ("risco levantado pelo manual (elaboração própria) — não é "
               "norma nem precedente"),
    "modelos": ("modelo ou checklist sugerido pelo manual — não é norma nem "
                "precedente"),
    "figura": "figura do manual, sem texto extraível",
    "outro": "quadro do manual, sem categoria própria",
}

NATUREZA_PROSA = ("orientação do manual (texto da Secretaria-Geral da "
                  "Presidência do TCU) — NÃO é decisão do Tribunal e não vincula")


def _url_busca(numero: str, ano: int | None, colegiado: str | None) -> str:
    """Consulta canonica no portal do TCU, montada aqui.

    Nao e permalink: o portal do TCU nao publica um. Boa parte dos links do
    proprio manual e busca por texto livre, que erra mais que esta, montada por
    numero e ano.
    """
    partes = [f"NUMACORDAO:{numero}"]
    if ano:
        partes.append(f"ANOACORDAO:{ano}")
    if colegiado:
        partes.append(f'COLEGIADO:"{colegiado}"')
    consulta = quote(quote(" ".join(partes), safe=""), safe="")
    ordem = quote(quote("DTRELEVANCIA desc, NUMACORDAOINT desc", safe=""), safe="")
    return ("https://pesquisa.apps.tcu.gov.br/#/documento/acordao-completo/*/"
            f"{consulta}/{ordem}/0/")


def _url_sumula(numero: str) -> str:
    consulta = quote(quote(f"NUMSUMULA:{numero}", safe=""), safe="")
    return ("https://pesquisa.apps.tcu.gov.br/#/documento/sumula/*/"
            f"{consulta}/%2520/0/")


def _avisos_julgado(ano: int | None, especie: str) -> list[str]:
    avisos = []
    if ano and ano < ANO_NLLC:
        avisos.append(
            f"Julgado em {ano}, ANTES da Lei 14.133/2021 (em vigor desde "
            f"01/04/2021). O manual o traz por entender que a tese sobrevive à "
            f"mudança de lei, mas isso é opinião do manual — o enunciado não "
            f"diz sob qual lei foi firmado. Confira o inteiro teor antes de "
            f"apresentá-lo como entendimento sob a lei nova.")
    elif ano == ANO_NLLC:
        avisos.append(
            "Julgado em 2021, ano da entrada em vigor da Lei 14.133/2021. O "
            "caso pode ter sido decidido sob a Lei 8.666/1993, que conviveu "
            "com ela até 2023. Confira no inteiro teor.")
    if especie == "sumula":
        avisos.append(
            "Súmula do TCU: vincula a Administração federal no âmbito do "
            "controle externo, com peso maior que o de um acórdão isolado.")
    avisos.append(
        "O manual é a 5ª edição (2025): não alcança julgado posterior que "
        "tenha alterado o entendimento.")
    return avisos


def _citacao_secao(r: sqlite3.Row) -> str:
    return (f"TCU, Licitações & Contratos: Orientações e Jurisprudência, "
            f"5. ed., 2025, item {r['numero']} ({r['titulo']}), p. "
            f"{r['pagina_impressa']}")


def _secao_de(secao_id: int) -> sqlite3.Row:
    return con().execute("SELECT * FROM secao WHERE id = ?", [secao_id]).fetchone()


def _onde(r: sqlite3.Row) -> dict:
    return {"secao": r["numero"], "titulo": r["titulo"],
            "capitulo": r["capitulo"], "pagina_impressa": r["pagina_impressa"],
            "url": r["url"]}


def _trecho(texto: str, consulta: str, tamanho: int = 420) -> str:
    """Recorta em volta do primeiro termo da consulta, sem cortar palavra."""
    alvo = None
    for t in _termos(consulta):
        r = _radical(t)
        m = re.search(re.escape(r), texto, re.I)
        if m:
            alvo = m.start()
            break
    if alvo is None:
        return texto[:tamanho] + ("…" if len(texto) > tamanho else "")
    ini = max(0, alvo - tamanho // 3)
    fim = min(len(texto), ini + tamanho)
    corte = texto[ini:fim]
    if ini:
        corte = "…" + corte.split(" ", 1)[-1]
    if fim < len(texto):
        corte = corte.rsplit(" ", 1)[0] + "…"
    return corte


# ---------------------------------------------------------------------------
# Ferramentas.


@mcp.tool()
def pesquisar_orientacao(consulta: str, capitulo: str = "", limite: int = 10) -> dict:
    """Procura na PROSA do manual — o que o TCU orienta a fazer.

    É texto didático da Secretaria-Geral da Presidência do TCU, não decisão do
    Tribunal. Para o que o Tribunal decidiu, use `pesquisar_jurisprudencia`.
    """
    onde = "WHERE fts_secao MATCH ?"
    args: list = []
    if capitulo:
        onde += " AND s.capitulo = ?"
        args.append(str(capitulo).split(".")[0])
    sql = (f"SELECT s.*, snippet(fts_secao,1,'','','…',28) trecho "
           f"FROM fts_secao JOIN secao s ON s.id = fts_secao.rowid "
           f"{onde} ORDER BY rank LIMIT ?")
    linhas, expressao, relaxamento = _buscar(sql, consulta, args, limite)
    c = con()
    itens = []
    for r in linhas:
        conta = c.execute(
            "SELECT (SELECT COUNT(*) FROM julgado WHERE secao_id=?) j, "
            "(SELECT COUNT(*) FROM quadro WHERE secao_id=? AND categoria='riscos') k",
            [r["id"], r["id"]]).fetchone()
        itens.append({
            "citacao": _citacao_secao(r),
            **_onde(r),
            "natureza": NATUREZA_PROSA,
            "trecho": _trecho(r["texto"], consulta),
            "julgados_citados_nesta_secao": conta["j"],
            "quadros_de_risco_nesta_secao": conta["k"],
            "para_ler_inteira": f"ler_secao('{r['numero']}')",
        })
    return {"consulta": consulta, "expressao_executada": expressao,
            "relaxamento": relaxamento, "encontrados": len(itens),
            "secoes": itens,
            "aviso": ("Isto é a orientação do manual, não decisão do TCU. "
                      "O que o Tribunal firmou está nos quadros de "
                      "jurisprudência.")}


@mcp.tool()
def pesquisar_jurisprudencia(consulta: str, apenas_de_2021_em_diante: bool = False,
                             colegiado: str = "", limite: int = 10) -> dict:
    """Procura nos ENUNCIADOS dos julgados que o manual cita.

    `apenas_de_2021_em_diante` filtra os julgados posteriores à entrada em vigor
    da Lei 14.133/2021 — 269 dos 1.161. Use quando a pergunta for sobre a lei
    nova, e diga ao usuário que filtrou.
    """
    onde = "WHERE fts_julgado MATCH ?"
    args: list = []
    if apenas_de_2021_em_diante:
        onde += " AND j.ano >= ?"
        args.append(ANO_NLLC)
    if colegiado:
        onde += " AND j.colegiado LIKE ?"
        args.append(f"%{colegiado}%")
    sql = (f"SELECT j.* FROM fts_julgado JOIN julgado j ON j.id = fts_julgado.rowid "
           f"{onde} ORDER BY rank LIMIT ?")
    # O limite vale para julgados DISTINTOS, nao para linhas: o manual repete a
    # mesma tese em capitulos diferentes — 92 grupos, medido. Devolver o mesmo
    # acordao duas vezes gasta o limite e parece dois precedentes.
    linhas, expressao, relaxamento = _buscar(sql, consulta, args, limite * 3)
    agrupado: dict[tuple, dict] = {}
    for r in linhas:
        chave = (r["numero"], r["ano"], r["enunciado"])
        s = _secao_de(r["secao_id"])
        if chave in agrupado:
            agrupado[chave]["onde_no_manual"].append(_onde(s))
            continue
        if len(agrupado) >= limite:
            continue
        url = (_url_sumula(r["numero"]) if r["especie"] == "sumula"
               else _url_busca(r["numero"], r["ano"], r["colegiado"]))
        agrupado[chave] = {
            "citacao": r["citacao"],
            "especie": r["especie"],
            "ano": r["ano"],
            "colegiado": r["colegiado"],
            "enunciado": r["enunciado"],
            "natureza": NATUREZA["jurisprudencia"],
            "onde_no_manual": [_onde(s)],
            "citacao_do_manual": _citacao_secao(s),
            "url_busca_no_tcu": url,
            "url_publicada_no_manual": r["url"],
            "avisos": _avisos_julgado(r["ano"], r["especie"]),
        }
    itens = list(agrupado.values())
    for i in itens:
        i["citado_em_quantas_secoes"] = len(i["onde_no_manual"])
    antigos = sum(1 for i in itens if i["ano"] and i["ano"] < ANO_NLLC)
    return {
        "consulta": consulta, "expressao_executada": expressao,
        "relaxamento": relaxamento, "encontrados": len(itens),
        "anteriores_a_2021": antigos,
        "filtro_aplicado": ("somente julgados de 2021 em diante"
                            if apenas_de_2021_em_diante else "nenhum"),
        "julgados": itens,
        "aviso": ("Os links são CONSULTAS de busca no portal do TCU, não "
                  "permalinks: o portal não publica um. Confira o inteiro teor "
                  "antes de citar numa peça."),
    }


@mcp.tool()
def ler_secao(numero: str, incluir_quadros: bool = True) -> dict:
    """Devolve uma seção inteira: prosa, quadros com suas linhas, e notas.

    `numero` é o item do manual, como "3.2" ou "5.10.2.19".
    """
    c = con()
    s = c.execute("SELECT * FROM secao WHERE numero = ?",
                  [str(numero).strip().rstrip(".")]).fetchone()
    if not s:
        prox = [r["numero"] for r in c.execute(
            "SELECT numero FROM secao WHERE numero LIKE ? LIMIT 8",
            [f"{numero}%"])]
        return {"erro": f"seção {numero} não existe no manual",
                "talvez_seja": prox}
    blocos = [{"tipo": b["tipo"], "texto": b["texto"]} for b in c.execute(
        "SELECT tipo,texto FROM bloco WHERE secao_id=? ORDER BY ordem", [s["id"]])]
    notas = [{"numero": n["numero"], "texto": n["texto"]} for n in c.execute(
        "SELECT numero,texto FROM nota WHERE secao_id=? ORDER BY numero", [s["id"]])]
    quadros = []
    if incluir_quadros:
        for q in c.execute("SELECT * FROM quadro WHERE secao_id=? ORDER BY ordem",
                           [s["id"]]):
            # A 1a linha e o cabecalho da tabela: sai como nome das colunas,
            # nao como conteudo. Sem isso, "Riscos" vira um risco.
            cab = c.execute(
                "SELECT colunas_json FROM linha WHERE quadro_id=? AND cabecalho=1",
                [q["id"]]).fetchone()
            linhas = [{"rotulo": l["rotulo"], "conteudo": l["conteudo"]}
                      for l in c.execute(
                          "SELECT rotulo,conteudo FROM linha WHERE quadro_id=? "
                          "AND cabecalho=0 ORDER BY ordem", [q["id"]])]
            quadros.append({
                "legenda": f"{q['especie']} {q['numero']} – {q['titulo']}"
                           if q["numero"] else q["titulo"],
                "categoria": q["categoria"],
                "natureza": NATUREZA.get(q["categoria"], NATUREZA["outro"]),
                "pagina_impressa": q["pagina_impressa"],
                "fonte_declarada": q["fonte"],
                "colunas": json.loads(cab["colunas_json"]) if cab else None,
                "linhas": linhas,
            })
    filhas = [{"numero": f["numero"], "titulo": f["titulo"]} for f in c.execute(
        "SELECT numero,titulo FROM secao WHERE numero_pai=? ORDER BY ordem",
        [s["numero"]])]
    return {
        "citacao": _citacao_secao(s), **_onde(s),
        "natureza_da_prosa": NATUREZA_PROSA,
        "blocos": blocos, "quadros": quadros, "notas_de_rodape": notas,
        "subsecoes": filhas,
        "coletado_em": c.execute("SELECT coletado_em FROM obra").fetchone()[0],
    }


@mcp.tool()
def sumario(capitulo: str = "", profundidade: int = 3) -> dict:
    """O sumário do manual, com a página impressa de cada item.

    Sem `capitulo`, devolve a estrutura toda até `profundidade`.
    """
    args: list = [profundidade]
    onde = "WHERE nivel <= ?"
    if capitulo:
        onde += " AND capitulo = ?"
        args.append(str(capitulo).split(".")[0])
    itens = [{"numero": r["numero"], "titulo": r["titulo"], "nivel": r["nivel"],
              "pagina_impressa": r["pagina_impressa"],
              "julgados": r["n"], "chars": r["chars"]}
             for r in con().execute(
                 f"SELECT s.*, (SELECT COUNT(*) FROM julgado WHERE secao_id=s.id) n "
                 f"FROM secao s {onde} ORDER BY ordem", args)]
    return {"itens": itens, "quantos": len(itens)}


@mcp.tool()
def riscos_de(consulta: str = "", secao: str = "", limite: int = 12) -> dict:
    """Os riscos que o manual levanta — 115 quadros, 508 riscos.

    Elaboração própria do manual sobre o que costuma dar errado em cada etapa.
    Não é norma nem precedente. Use `secao` para os riscos de um item, ou
    `consulta` para procurar por assunto.
    """
    return _quadros("riscos", consulta, secao, limite)


@mcp.tool()
def modelos_e_checklists(consulta: str = "", secao: str = "",
                         limite: int = 12) -> dict:
    """Os modelos e checklists que o manual indica — 41 quadros, 140 linhas.

    São sugestões do manual, não minutas obrigatórias.
    """
    return _quadros("modelos", consulta, secao, limite)


@mcp.tool()
def referencias_normativas(consulta: str = "", secao: str = "",
                           limite: int = 12) -> dict:
    """Os dispositivos legais que o manual transcreve — 158 quadros, 1.005 linhas.

    A autoridade é da lei, não do TCU. E o texto está na redação da data da
    edição (2025): alteração posterior não se reflete aqui.
    """
    return _quadros("referencias_normativas", consulta, secao, limite)


def _quadros(categoria: str, consulta: str, secao: str, limite: int) -> dict:
    c = con()
    if secao:
        s = c.execute("SELECT * FROM secao WHERE numero = ?",
                      [str(secao).strip().rstrip(".")]).fetchone()
        if not s:
            return {"erro": f"seção {secao} não existe no manual"}
        linhas = c.execute(
            "SELECT l.*, q.titulo qt, q.numero qn, q.especie qe, q.fonte qf, "
            "q.pagina_impressa qp, q.secao_id FROM linha l "
            "JOIN quadro q ON q.id = l.quadro_id "
            "WHERE q.categoria = ? AND q.secao_id = ? AND l.cabecalho = 0 "
            "ORDER BY q.ordem, l.ordem",
            [categoria, s["id"]]).fetchall()
        expressao = relaxamento = ""
    elif consulta:
        sql = ("SELECT l.*, q.titulo qt, q.numero qn, q.especie qe, q.fonte qf, "
               "q.pagina_impressa qp, q.secao_id FROM fts_linha "
               "JOIN linha l ON l.id = fts_linha.rowid "
               "JOIN quadro q ON q.id = l.quadro_id "
               "WHERE fts_linha MATCH ? AND q.categoria = ? "
               "ORDER BY rank LIMIT ?")
        linhas, expressao, relaxamento = _buscar(sql, consulta, [categoria], limite)
    else:
        return {"erro": "informe `consulta` ou `secao`"}

    itens = []
    for r in linhas:
        s = _secao_de(r["secao_id"])
        itens.append({
            "texto": r["conteudo"],
            "rotulo": r["rotulo"] if r["n_colunas"] > 1 else None,
            "quadro": (f"{r['qe']} {r['qn']} – {r['qt']}" if r["qn"] else r["qt"]),
            "pagina_impressa": r["qp"],
            "natureza": NATUREZA[categoria],
            "fonte_declarada": r["qf"],
            "onde_no_manual": _onde(s),
            "citacao": _citacao_secao(s),
        })
    return {"categoria": categoria, "consulta": consulta or None,
            "secao": secao or None, "expressao_executada": expressao,
            "relaxamento": relaxamento, "encontrados": len(itens),
            "linhas": itens}


@mcp.tool()
def julgado_no_manual(numero: str, ano: int = 0) -> dict:
    """Onde o manual cita um acórdão, e para quê.

    Serve para a pergunta inversa: tenho este acórdão na mão — o manual do TCU
    o usa, e em que contexto?
    """
    num = re.sub(r"[^0-9]", "", str(numero))
    sql = "SELECT * FROM julgado WHERE numero = ?"
    args: list = [num]
    if ano:
        sql += " AND ano = ?"
        args.append(int(ano))
    linhas = con().execute(sql + " ORDER BY ano", args).fetchall()
    if not linhas:
        return {"encontrado": False, "numero": num, "ano": ano or None,
                "o_que_isso_significa": (
                    "Este acórdão não é citado na 5ª edição do manual. Isso NÃO "
                    "significa que o TCU não o proferiu nem que ele seja "
                    "irrelevante — significa que o manual não o trouxe.")}
    itens = []
    for r in linhas:
        s = _secao_de(r["secao_id"])
        itens.append({
            "citacao": r["citacao"], "ano": r["ano"],
            "colegiado": r["colegiado"], "enunciado": r["enunciado"],
            "onde_no_manual": _onde(s), "citacao_do_manual": _citacao_secao(s),
            "url_busca_no_tcu": _url_busca(r["numero"], r["ano"], r["colegiado"]),
            "avisos": _avisos_julgado(r["ano"], r["especie"]),
        })
    return {"encontrado": True, "quantas_vezes": len(itens), "ocorrencias": itens}


@mcp.tool()
def ler_pagina(pagina_impressa: int) -> dict:
    """O texto de uma página do PDF publicado, pela numeração impressa.

    Serve para conferir uma citação por página. Atenção: no PDF do TCU parte do
    corpo foi colada como IMAGEM, e nessas páginas o texto vem incompleto — o
    campo `rasterizada` avisa. O texto íntegro dessas seções está em `ler_secao`.
    """
    r = con().execute("SELECT * FROM pagina WHERE pagina_impressa = ?",
                      [int(pagina_impressa)]).fetchone()
    if not r:
        return {"erro": f"página impressa {pagina_impressa} não existe",
                "faixa": "1 a 1031"}
    s = con().execute(
        "SELECT * FROM secao WHERE pagina_impressa <= ? ORDER BY pagina_impressa "
        "DESC, ordem DESC LIMIT 1", [int(pagina_impressa)]).fetchone()
    saida = {"pagina_impressa": r["pagina_impressa"],
             "pagina_no_pdf": r["pagina_pdf"], "texto": r["texto"],
             "chars": r["chars"],
             "secao_provavel": _onde(s) if s else None}
    if r["rasterizada"]:
        saida["aviso"] = (
            "Esta página do PDF teve o corpo colado como IMAGEM: o texto acima "
            f"está incompleto ({r['chars']} caracteres, {r['area_imagem_pct']}% "
            "da mancha em imagem). O conteúdo íntegro está na seção "
            "correspondente, pela versão interativa do manual.")
    return saida


@mcp.tool()
def cobertura_do_acervo() -> dict:
    """O que esta base tem, de onde veio e o que ela não alcança."""
    c = con()
    um = lambda sql, *a: c.execute(sql, a).fetchone()[0]
    obra = c.execute("SELECT * FROM obra").fetchone()
    return {
        "obra": {
            "titulo": obra["titulo"], "edicao": obra["edicao"],
            "ano": obra["ano"], "orgao": obra["orgao"],
            "site": obra["url_site"], "pdf": obra["url_pdf"],
            "paginas_impressas": 1031,
        },
        "coletado_em": obra["coletado_em"],
        "conteudo": {
            "secoes": um("SELECT COUNT(*) FROM secao"),
            "paragrafos": um("SELECT COUNT(*) FROM bloco"),
            "quadros": um("SELECT COUNT(*) FROM quadro"),
            "linhas_de_quadro": um("SELECT COUNT(*) FROM linha"),
            "notas_de_rodape": um("SELECT COUNT(*) FROM nota"),
            "referencias_bibliograficas": um("SELECT COUNT(*) FROM referencia"),
            "quadros_por_categoria": {
                r[0]: r[1] for r in c.execute(
                    "SELECT categoria, COUNT(*) FROM quadro GROUP BY categoria "
                    "ORDER BY 2 DESC")},
        },
        "jurisprudencia": {
            "julgados_citados": um("SELECT COUNT(*) FROM julgado"),
            "acordaos_distintos": um(
                "SELECT COUNT(DISTINCT numero||'/'||COALESCE(ano,0)) FROM julgado "
                "WHERE especie='acordao'"),
            "sumulas_distintas": um(
                "SELECT COUNT(DISTINCT numero) FROM julgado WHERE especie='sumula'"),
            "periodo": [um("SELECT MIN(ano) FROM julgado WHERE ano"),
                        um("SELECT MAX(ano) FROM julgado WHERE ano")],
            "anteriores_a_2021": um(
                "SELECT COUNT(*) FROM julgado WHERE anterior_a_14133=1"),
            "de_2021_em_diante": um(
                "SELECT COUNT(*) FROM julgado WHERE anterior_a_14133=0"),
            "por_colegiado": {r[0] or "não declarado": r[1] for r in c.execute(
                "SELECT colegiado, COUNT(*) FROM julgado GROUP BY colegiado "
                "ORDER BY 2 DESC")},
        },
        "de_onde_veio": {
            r["chave"]: r["valor"] for r in c.execute(
                "SELECT chave,valor FROM nota_de_coleta")},
        "o_que_nao_alcanca": [
            "Não é a jurisprudência do TCU: é a seleção da 5ª edição do manual.",
            "Não alcança julgado posterior a 2025.",
            "Não é a lei: transcreve dispositivos na redação de 2025.",
            "Não tem link para inteiro teor de acórdão — o portal do TCU não "
            "publica permalink; o que há é consulta de busca.",
        ],
    }


@mcp.tool()
def pontos_cegos() -> dict:
    """Onde a busca não enxerga. Resultado vazio num destes não prova nada."""
    c = con()
    um = lambda sql: c.execute(sql).fetchone()[0]
    figuras = [{"legenda": f"{r['especie']} {r['numero']} – {r['titulo']}",
                "secao": r["numero_secao"], "pagina": r["pagina_impressa"]}
               for r in c.execute(
                   "SELECT q.*, s.numero numero_secao FROM quadro q "
                   "JOIN secao s ON s.id=q.secao_id WHERE q.so_imagem=1 "
                   "ORDER BY q.numero")]
    return {
        "figuras_sem_texto": {
            "quantas": len(figuras),
            "o_que_significa": ("são diagramas: existem no manual e a busca não "
                                "alcança o que está desenhado dentro deles"),
            "quais": figuras},
        "linhas_que_nao_sao_precedente": {
            "quantas": um("SELECT COUNT(*) FROM linha l JOIN quadro q "
                          "ON q.id=l.quadro_id WHERE q.categoria='jurisprudencia' "
                          "AND l.rotulo LIKE '%esquisa de %urisprud%'"),
            "o_que_significa": ("linhas dos quadros de jurisprudência que dizem "
                                "'Pesquisa de Jurisprudência': são sugestão de "
                                "busca no portal do TCU, não julgado. Não "
                                "aparecem como julgado neste acervo.")},
        "paginas_rasterizadas_no_pdf": {
            "quantas": um("SELECT COUNT(*) FROM pagina WHERE rasterizada=1"),
            "o_que_significa": ("no PDF publicado o corpo dessas páginas foi "
                                "colado como imagem. `ler_pagina` devolve texto "
                                "incompleto nelas; o conteúdo íntegro está em "
                                "`ler_secao`, que vem da versão interativa.")},
        "julgados_sem_colegiado": um(
            "SELECT COUNT(*) FROM julgado WHERE colegiado IS NULL"),
        "secoes_sem_prosa_propria": [
            r[0] for r in c.execute("SELECT numero FROM secao WHERE chars < 50")],
    }


@mcp.tool()
def search(query: str) -> dict:
    """Busca geral no manual — orientação e jurisprudência."""
    o = pesquisar_orientacao(query, limite=5)
    j = pesquisar_jurisprudencia(query, limite=5)
    return {"results": [
        {"id": f"secao:{s['secao']}", "title": s["citacao"],
         "text": s["trecho"], "url": s["url"]} for s in o["secoes"]
    ] + [
        {"id": f"julgado:{r['citacao']}", "title": r["citacao"],
         "text": r["enunciado"][:1200], "url": r["url_busca_no_tcu"]}
        for r in j["julgados"]]}


@mcp.tool()
def fetch(id: str) -> dict:
    """Recupera o conteúdo integral de um resultado devolvido por `search`."""
    alvo = str(id)
    if alvo.startswith("secao:"):
        s = ler_secao(alvo.split(":", 1)[1])
        if "erro" in s:
            return {"id": id, "title": "não encontrado", "text": "", "url": ""}
        corpo = "\n\n".join(b["texto"] for b in s["blocos"])
        return {"id": id, "title": s["citacao"], "url": s["url"],
                "text": f"{s['natureza_da_prosa']}\n\n{corpo}"}
    if alvo.startswith("julgado:"):
        rot = alvo.split(":", 1)[1]
        m = re.search(r"(\d+)/(\d{4})", rot)
        if m:
            r = julgado_no_manual(m.group(1), int(m.group(2)))
            if r.get("encontrado"):
                o = r["ocorrencias"][0]
                return {"id": id, "title": o["citacao"],
                        "url": o["url_busca_no_tcu"],
                        "text": o["enunciado"] + "\n\n" + "\n".join(o["avisos"])}
    return {"id": id, "title": "não encontrado", "text": "", "url": ""}


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    if modo == "http":
        alcance = ", ".join(_dominios()) or "somente local"
        print(f"Manual TCU em http://{mcp.settings.host}:{mcp.settings.port}/mcp"
              f"  ({alcance})", file=sys.stderr)
    mcp.run(transport="streamable-http" if modo == "http" else "stdio")
