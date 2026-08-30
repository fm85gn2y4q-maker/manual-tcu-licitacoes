"""Sobe o .mcpb DESEMPACOTADO por stdio e conversa MCP de verdade com ele.

Empacotar nao prova nada. O que se quer saber e se a extensao que o Claude
Desktop vai instalar realmente inicializa, lista as ferramentas e responde a
uma chamada — com as dependencias do proprio pacote, nao com as do venv.

Por que Popen e nao subprocess.run: despejando os pedidos de uma vez e fechando
a entrada, o servidor ve EOF e encerra ANTES de escrever a ultima resposta.
Medido: cinco pedidos, cinco processados no log, quatro respostas escritas. O
cliente real mantem o canal aberto, e e isso que este ensaio faz — cada pedido
espera a sua resposta antes do proximo.
"""
import json
import subprocess
import sys
import threading
from pathlib import Path
from queue import Empty, Queue

RAIZ = Path(__file__).resolve().parent
PACOTE = RAIZ / "build" / "mcpb"
ENTRADA = PACOTE / "server" / "main.py"

falhas = []


def checa(nome, ok, detalhe=""):
    print(("  OK   " if ok else "  FALHA") + "  " + nome +
          (("  -> " + str(detalhe)) if detalhe else ""))
    if not ok:
        falhas.append(nome)


class Sessao:
    def __init__(self, exe):
        self.p = subprocess.Popen(
            [exe, str(ENTRADA)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
            errors="replace", bufsize=1)
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

    def notificar(self, metodo, params=None):
        self._enviar({"jsonrpc": "2.0", "method": metodo, "params": params or {}})

    def pedir(self, metodo, params=None, espera=120):
        self._id += 1
        alvo = self._id
        self._enviar({"jsonrpc": "2.0", "id": alvo, "method": metodo,
                      "params": params or {}})
        while True:
            try:
                m = self.fila.get(timeout=espera)
            except Empty:
                raise TimeoutError(f"sem resposta para {metodo}")
            if m.get("id") == alvo:
                return m

    def chamar(self, ferramenta, **argumentos):
        r = self.pedir("tools/call",
                       {"name": ferramenta, "arguments": argumentos})
        if "error" in r:
            return {"__erro__": r["error"]}
        return json.loads(r["result"]["content"][0]["text"])

    def encerrar(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=20)
        except Exception:
            self.p.kill()


def main():
    if not ENTRADA.exists():
        print("pacote nao construido — rode empacotar_mcpb.py", file=sys.stderr)
        return 1
    manifesto = json.loads((PACOTE / "manifest.json").read_text(encoding="utf-8"))
    exe = manifesto["server"]["mcp_config"]["command"]
    print("interpretador do manifesto:", exe)
    print("acervo no pacote: %.1f MB" % (
        (PACOTE / "dados" / "manual_tcu.sqlite3").stat().st_size / 1e6))
    print()

    s = Sessao(exe)
    try:
        r = s.pedir("initialize", {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "conferir", "version": "1"}})
        s.notificar("notifications/initialized")
        info = r["result"]["serverInfo"]
        checa("identificou-se como manual-tcu-licitacoes",
              info["name"] == "manual-tcu-licitacoes", info)
        instr = r["result"].get("instructions") or ""
        checa("entregou as instrucoes com a regra central",
              "O MANUAL NÃO É O TRIBUNAL" in instr, "%d chars" % len(instr))
        checa("as instrucoes declaram os 74% de julgados antigos",
              "74%" in instr)

        nomes = [t["name"] for t in s.pedir("tools/list")["result"]["tools"]]
        checa("listou as 13 ferramentas", len(nomes) == 13, len(nomes))
        checa("o manifesto declara exatamente as ferramentas que existem",
              {t["name"] for t in manifesto["tools"]} == set(nomes),
              {t["name"] for t in manifesto["tools"]} ^ set(nomes))

        c = s.chamar("cobertura_do_acervo")
        checa("cobertura_do_acervo leu o banco empacotado",
              c["conteudo"]["secoes"] == 210, c.get("__erro__") or
              c["conteudo"]["secoes"])
        checa("declara os 860 julgados anteriores a 2021",
              c["jurisprudencia"]["anteriores_a_2021"] == 860)

        j = s.chamar("pesquisar_jurisprudencia",
                     consulta="aditivo contratual acima do limite legal", limite=4)
        checa("pesquisar_jurisprudencia respondeu", j.get("encontrados", 0) > 0,
              j.get("__erro__") or j.get("encontrados"))
        antigos = [x for x in j["julgados"] if x["ano"] and x["ano"] < 2021]
        checa("os julgados antigos vem com o aviso de regime",
              all(any("ANTES da Lei 14.133/2021" in a for a in x["avisos"])
                  for x in antigos), "%d anteriores de %d"
              % (len(antigos), j["encontrados"]))
        for x in j["julgados"]:
            print("     %-36s %s" % (x["citacao"][:36], x["enunciado"][:64]))

        sec = s.chamar("ler_secao", numero="3.2")
        corpo = " ".join(b["texto"] for b in sec["blocos"])
        checa("ler_secao traz o texto que falta no PDF",
              "afastando favoritismos" in corpo)
        checa("ler_secao devolve o cabecalho como nome de coluna",
              any(q.get("colunas") for q in sec["quadros"]))

        rk = s.chamar("riscos_de", secao="4.3", limite=5)
        checa("riscos_de respondeu", rk.get("encontrados", 0) > 0,
              rk.get("__erro__") or rk.get("encontrados"))

        p = s.chamar("ler_pagina", pagina_impressa=149)
        checa("ler_pagina avisa que a pagina esta rasterizada no PDF", "aviso" in p)
    finally:
        s.encerrar()

    print()
    if falhas:
        print("FALHAS: %d" % len(falhas))
        for f in falhas:
            print("  -", f)
        return 1
    print("O PACOTE SOBE, LISTA E RESPONDE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
