"""Conversa MCP com a extensao JA INSTALADA no Claude Desktop.

Diferente de conferir_pacote.py, que exercita o build. Aqui se roda o que esta
em `%APPDATA%\\Claude\\Claude Extensions\\...`, com o interpretador que o
manifesto fixou — a mesma linha de comando que o Claude Desktop vai executar,
com `${__dirname}` resolvido para a pasta instalada.

Exercita as 13 ferramentas com perguntas de procurador, nao com chamadas vazias:
uma ferramenta que responde `{}` sem erro passaria num teste de fumaca e seria
inutil na conversa.
"""
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from queue import Empty, Queue

ID = "local.mcpb.matheus-menegatti.manual-tcu-licitacoes"
INSTALADO = (Path.home() / "AppData" / "Roaming" / "Claude" /
             "Claude Extensions" / ID)

falhas = []


def checa(nome, ok, detalhe=""):
    print(("  OK   " if ok else "  FALHA") + "  " + nome +
          (("  -> " + str(detalhe)) if detalhe else ""))
    if not ok:
        falhas.append(nome)


def titulo(t):
    print()
    print("-" * 74)
    print(t)
    print("-" * 74)


class Sessao:
    def __init__(self, comando, args):
        self.p = subprocess.Popen(
            [comando] + args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
            errors="replace", bufsize=1, cwd=str(INSTALADO))
        self.fila = Queue()
        threading.Thread(target=self._ler, daemon=True).start()
        self._id = 0

    def _ler(self):
        for linha in self.p.stdout:
            linha = linha.strip()
            if linha:
                try:
                    self.fila.put(json.loads(linha))
                except json.JSONDecodeError:
                    pass

    def _enviar(self, msg):
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()

    def notificar(self, metodo):
        self._enviar({"jsonrpc": "2.0", "method": metodo, "params": {}})

    def pedir(self, metodo, params=None, espera=120):
        self._id += 1
        alvo = self._id
        self._enviar({"jsonrpc": "2.0", "id": alvo, "method": metodo,
                      "params": params or {}})
        while True:
            try:
                m = self.fila.get(timeout=espera)
            except Empty:
                raise TimeoutError("sem resposta para " + metodo)
            if m.get("id") == alvo:
                return m

    def chamar(self, ferramenta, **argumentos):
        t0 = time.time()
        r = self.pedir("tools/call", {"name": ferramenta,
                                      "arguments": argumentos})
        ms = (time.time() - t0) * 1000
        if "error" in r:
            return {"__erro__": r["error"]}, ms
        return json.loads(r["result"]["content"][0]["text"]), ms

    def encerrar(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=20)
        except Exception:
            self.p.kill()


def main():
    if not (INSTALADO / "manifest.json").exists():
        print("extensao nao instalada em " + str(INSTALADO), file=sys.stderr)
        return 1
    man = json.loads((INSTALADO / "manifest.json").read_text(encoding="utf-8"))
    cfg = man["server"]["mcp_config"]
    comando = cfg["command"]
    args = [a.replace("${__dirname}", str(INSTALADO)) for a in cfg["args"]]
    print("extensao :", ID)
    print("comando  :", comando)
    print("entrada  :", args[0])
    print()

    s = Sessao(comando, args)
    exercitadas = set()
    try:
        titulo("HANDSHAKE")
        r = s.pedir("initialize", {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "conferir-instalado", "version": "1"}})
        s.notificar("notifications/initialized")
        checa("o servidor subiu do lugar instalado",
              r["result"]["serverInfo"]["name"] == "manual-tcu-licitacoes")
        instr = r["result"].get("instructions") or ""
        checa("as instrucoes chegam com a regra central",
              "O MANUAL NÃO É O TRIBUNAL" in instr and "74%" in instr,
              "%d chars" % len(instr))
        nomes = [t["name"] for t in s.pedir("tools/list")["result"]["tools"]]
        checa("as 13 ferramentas aparecem", len(nomes) == 13, len(nomes))

        titulo("PERGUNTA 1 — 'posso aditar um contrato em mais de 25%?'")
        j, ms = s.chamar("pesquisar_jurisprudencia",
                         consulta="acrescimo contratual limite 25%", limite=4)
        exercitadas.add("pesquisar_jurisprudencia")
        checa("achou precedente", j.get("encontrados", 0) > 0,
              "%d em %.0f ms" % (j.get("encontrados", 0), ms))
        for x in j.get("julgados", []):
            print("   %-34s (%s) %s" % (x["citacao"][:34],
                  "ANTES da 14.133" if x["ano"] and x["ano"] < 2021 else "pos-14.133",
                  x["enunciado"][:58]))
        antigos = [x for x in j["julgados"] if x["ano"] and x["ano"] < 2021]
        checa("os anteriores a 2021 vem com aviso de regime",
              all(any("ANTES da Lei 14.133/2021" in a for a in x["avisos"])
                  for x in antigos), "%d de %d" % (len(antigos), j["encontrados"]))
        checa("nenhum julgado se apresenta com link de inteiro teor",
              all(x["url_busca_no_tcu"].startswith("https://pesquisa.apps.tcu.gov.br")
                  for x in j["julgados"]))

        titulo("PERGUNTA 2 — 'o que o manual manda na pesquisa de precos?'")
        o, ms = s.chamar("pesquisar_orientacao",
                         consulta="pesquisa de precos cesta de precos", limite=3)
        exercitadas.add("pesquisar_orientacao")
        checa("achou secoes", o.get("encontrados", 0) > 0,
              "%d em %.0f ms" % (o.get("encontrados", 0), ms))
        checa("cada uma se declara orientacao, nao decisao",
              all("NÃO é decisão" in x["natureza"] for x in o["secoes"]))
        for x in o["secoes"]:
            print("   item %-10s p.%-5s %s" % (x["secao"], x["pagina_impressa"],
                                               x["titulo"][:48]))

        titulo("PERGUNTA 3 — ler a secao que o PDF perdeu (3.2, p.149)")
        sec, ms = s.chamar("ler_secao", numero="3.2")
        exercitadas.add("ler_secao")
        corpo = " ".join(b["texto"] for b in sec["blocos"])
        checa("traz a lista de principios que no PDF e imagem",
              "afastando favoritismos" in corpo, "%d chars em %.0f ms"
              % (len(corpo), ms))
        checa("traz as notas de rodape", len(sec["notas_de_rodape"]) >= 30,
              len(sec["notas_de_rodape"]))
        checa("a citacao sai pronta para a peca", "p. 149" in sec["citacao"])
        print("   " + sec["citacao"])

        titulo("PERGUNTA 4 — 'quais os riscos do termo de referencia?'")
        rk, ms = s.chamar("riscos_de", secao="4.3", limite=4)
        exercitadas.add("riscos_de")
        checa("achou riscos", rk.get("encontrados", 0) > 0,
              "%d em %.0f ms" % (rk.get("encontrados", 0), ms))
        checa("declara que risco nao e norma nem precedente",
              all("não é norma" in x["natureza"] for x in rk["linhas"]))
        for x in rk["linhas"][:2]:
            print("   -", x["texto"][:100])

        titulo("PERGUNTA 5 — 'o manual usa o Acordao 2622/2015?'")
        a, ms = s.chamar("julgado_no_manual", numero="2622", ano=2015)
        exercitadas.add("julgado_no_manual")
        checa("achou e diz onde", a.get("encontrado") and a["quantas_vezes"] >= 10,
              "%d ocorrencias em %.0f ms" % (a.get("quantas_vezes", 0), ms))
        print("   citado em: " + ", ".join(sorted(
            {o["onde_no_manual"]["secao"] for o in a["ocorrencias"]})))

        titulo("AS DEMAIS FERRAMENTAS")
        for nome, args_ in [
                ("sumario", {"capitulo": "5", "profundidade": 2}),
                ("modelos_e_checklists", {"consulta": "matriz de risco"}),
                ("referencias_normativas", {"consulta": "contratacao direta"}),
                ("ler_pagina", {"pagina_impressa": 149}),
                ("cobertura_do_acervo", {}),
                ("pontos_cegos", {}),
                ("search", {"query": "fiscalizacao do contrato"}),
                ("fetch", {"id": "secao:6.1.4"})]:
            d, ms = s.chamar(nome, **args_)
            exercitadas.add(nome)
            erro = d.get("__erro__") if isinstance(d, dict) else None
            checa(nome, erro is None and bool(d),
                  erro or "%.0f ms, %d chars" % (ms, len(json.dumps(d))))

        checa("as 13 ferramentas foram exercitadas", exercitadas == set(nomes),
              exercitadas ^ set(nomes))
    finally:
        s.encerrar()

    print()
    print("=" * 74)
    if falhas:
        print("FALHAS: %d" % len(falhas))
        for f in falhas:
            print("  -", f)
        return 1
    print("A EXTENSAO INSTALADA RESPONDE — 13/13 FERRAMENTAS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
