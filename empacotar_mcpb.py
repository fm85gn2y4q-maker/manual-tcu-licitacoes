"""Empacota o manual do TCU como extensão do Claude Desktop (.mcpb).

    python empacotar_mcpb.py [--banco CAMINHO] [--python EXE]

Gera `dist/manual-tcu-licitacoes.mcpb`. A extensão roda o servidor localmente por stdio,
instalada com um duplo clique: sem conta, sem túnel, sem depender de o PC estar
publicando nada.

O pacote leva as dependências junto (`server/lib`), porque o Claude Desktop não
instala nada — só executa o que está dentro. Leva também o acervo inteiro.

Herdado dos acervos anteriores, e cada item custou um erro lá:
  * dependências por versão de Python — `pydantic_core` é binário compilado, e
    o .pyd de cp312 não carrega no 3.13;
  * `pywin32` instalado com `--target` não roda o pós-instalação, e o `mcp`
    importa `pywintypes` no Windows;
  * caminho de interpretador com espaço quebra o `command` do manifesto;
  * `compatibility` fica fora do manifesto de propósito: foi a única chave que
    o Claude Desktop recusou, e sem validador é mais seguro declarar menos.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# O console do Windows é cp1252 e derruba o script num `print` com caractere
# fora da página. Falhar DEPOIS de empacotar com sucesso é o pior dos mundos:
# o artefato existe e o passo sai com código 1.
for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

RAIZ = Path(__file__).resolve().parent
CONSTRUCAO = RAIZ / "build" / "mcpb"
DESTINO = RAIZ / "dist" / "manual-tcu-licitacoes.mcpb"


VERSOES = ("3.12", "3.13", "3.14")

ENTRADA = '''"""Ponto de entrada da extensão: sobe o servidor por stdio."""
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent

MARCA = f"py{sys.version_info.major}{sys.version_info.minor}"
BIBLIOTECAS = AQUI / "lib" / MARCA
if not BIBLIOTECAS.is_dir():
    disponiveis = sorted(p.name for p in (AQUI / "lib").glob("py*"))
    print(
        f"Manual TCU: sem dependencias para Python "
        f"{sys.version_info.major}.{sys.version_info.minor}. "
        f"O pacote traz: {', '.join(disponiveis) or 'nenhuma'}.",
        file=sys.stderr,
    )
    raise SystemExit(1)

sys.path.insert(0, str(BIBLIOTECAS))
sys.path.insert(0, str(AQUI))

# O `mcp` importa `pywintypes` no Windows. Instalado com `pip --target`, o
# pywin32 nao roda seu pos-instalacao: os modulos ficam em `win32/lib` e as
# DLLs em `pywin32_system32`, nenhum dos dois alcancavel por padrao.
for _extra in ("win32", "pythonwin"):
    _caminho = BIBLIOTECAS / _extra
    if _caminho.is_dir():
        sys.path.insert(0, str(_caminho))
_lib_win32 = BIBLIOTECAS / "win32" / "lib"
if _lib_win32.is_dir():
    sys.path.insert(0, str(_lib_win32))

_dlls = BIBLIOTECAS / "pywin32_system32"
if _dlls.is_dir():
    os.add_dll_directory(str(_dlls))
    os.environ["PATH"] = str(_dlls) + os.pathsep + os.environ.get("PATH", "")

os.environ.setdefault("MANUAL_BANCO",
                      str(AQUI.parent / "dados" / "manual_tcu.sqlite3"))

import servidor  # noqa: E402

servidor.mcp.run(transport="stdio")
'''

MANIFESTO = {
    "manifest_version": "0.2",
    "name": "manual-tcu-licitacoes",
    "display_name": "Manual TCU — Licitações e Contratos",
    "version": "1.0.0",
    "description": "O manual “Licitações & Contratos: Orientações e Jurisprudência do TCU”, 5ª edição, com a página impressa de cada item e o regime do julgado citado.",
    "long_description": "Consulta a 5ª edição do manual de licitações e contratos do TCU: 210 seções, 484 quadros, 1.161 julgados citados e 1.513 notas de rodapé. Separa o que o manual ORIENTA do que o Tribunal DECIDIU — são coisas de autoridade diferente na mesma página — e avisa quando o julgado citado é anterior à Lei 14.133/2021, o que vale para 74% deles. O texto vem da versão interativa publicada pelo TCU, porque no PDF o corpo de 91 páginas foi colado como imagem e não tem camada de texto.",
    "author": {
        "name": "Matheus Menegatti"
    },
    "server": {
        "type": "python",
        "entry_point": "server/main.py",
        "mcp_config": {
            "command": "python",
            "args": [
                "${__dirname}/server/main.py"
            ],
            "env": {
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8"
            }
        }
    },
    "tools": [
        {
            "name": "pesquisar_orientacao",
            "description": "Procura na prosa do manual — o que o TCU orienta a fazer."
        },
        {
            "name": "pesquisar_jurisprudencia",
            "description": "Procura nos enunciados dos julgados que o manual cita."
        },
        {
            "name": "ler_secao",
            "description": "Uma seção inteira: prosa, quadros e notas de rodapé."
        },
        {
            "name": "sumario",
            "description": "O sumário, com a página impressa de cada item."
        },
        {
            "name": "riscos_de",
            "description": "Os riscos que o manual levanta em cada etapa."
        },
        {
            "name": "modelos_e_checklists",
            "description": "Os modelos e checklists indicados pelo manual."
        },
        {
            "name": "referencias_normativas",
            "description": "Os dispositivos legais que o manual transcreve."
        },
        {
            "name": "julgado_no_manual",
            "description": "Onde o manual cita um acórdão, e para quê."
        },
        {
            "name": "ler_pagina",
            "description": "O texto de uma página do PDF, pela numeração impressa."
        },
        {
            "name": "cobertura_do_acervo",
            "description": "Volumes, período e limites da base."
        },
        {
            "name": "pontos_cegos",
            "description": "Onde a busca não enxerga."
        },
        {
            "name": "search",
            "description": "Busca compatível com pesquisa profunda."
        },
        {
            "name": "fetch",
            "description": "Recupera um resultado pelo identificador."
        }
    ],
    "keywords": [
        "TCU",
        "licitações",
        "contratos administrativos",
        "Lei 14.133/2021",
        "direito administrativo",
        "controle externo",
        "contratações públicas"
    ]
}


def validar(pasta: Path) -> bool:
    """Passa o manifesto pelo validador oficial, se houver Node por perto.

    Empacotar não prova nada: um manifesto com uma chave fora do lugar zipa
    igual e só falha na hora de instalar, com mensagem que aparece na tela do
    usuário e não no build.

    Validador indisponível não é manifesto inválido: se o `npx` não roda, o que
    se sabe é que não se sabe — o pacote sai, com aviso.
    """
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        print("  aviso: npx ausente, manifesto NÃO validado.")
        return True
    resultado = subprocess.run(
        [npx, "--yes", "@anthropic-ai/mcpb", "validate", str(pasta / "manifest.json")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    saida = (resultado.stdout + resultado.stderr).strip()
    if resultado.returncode == 0:
        print("  manifesto válido.")
        return True
    if any(m in saida.lower() for m in ("invalid manifest", "unrecognized key", "validation")):
        print("  " + "\n  ".join(saida.splitlines()[-8:]))
        return False
    print("  aviso: o validador não pôde ser executado; manifesto NÃO validado.")
    return True


def sem_espacos(caminho: str) -> str | None:
    """Forma curta 8.3 quando o caminho tiver espaços.

    O Claude Desktop quebra o `command` do manifesto nos espaços: um
    interpretador em "C:\\Users\\Fulano Silva\\..." vira o comando
    "C:\\Users\\Fulano" com o resto virando argumento.
    """
    if " " not in caminho:
        return caminho
    import ctypes
    buffer = ctypes.create_unicode_buffer(1024)
    tamanho = ctypes.windll.kernel32.GetShortPathNameW(caminho, buffer, 1024)
    curto = buffer.value if tamanho else ""
    if curto and " " not in curto and Path(curto).exists():
        return curto
    return None


def conferir_interpretador(exe: str) -> bool:
    """Recusa um interpretador que não importe o que o servidor usa."""
    prova = "import sqlite3, asyncio, json, unicodedata; print('ok')"
    r = subprocess.run([exe, "-I", "-c", prova], capture_output=True, text=True)
    if r.returncode == 0:
        return True
    print(f"  {exe}\n  não serve: "
          f"{(r.stderr.strip().splitlines() or ['?'])[-1][:110]}", file=sys.stderr)
    return False


def empacotar(banco: Path, python: str | None = None) -> int:
    if python:
        if not Path(python).exists():
            print(f"Interpretador não encontrado: {python}", file=sys.stderr)
            return 1
        print("Conferindo o interpretador escolhido…")
        if not conferir_interpretador(python):
            return 1
        comando = sem_espacos(python)
        if comando is None:
            print(f"  O caminho tem espaços e não há nome curto 8.3 para ele:\n"
                  f"    {python}\n  O Claude Desktop quebraria o comando no "
                  f"primeiro espaço.", file=sys.stderr)
            return 1
        if comando != python and not conferir_interpretador(comando):
            return 1
        MANIFESTO["server"]["mcp_config"]["command"] = comando
        print("  fixado em", subprocess.run([comando, "--version"],
                                            capture_output=True, text=True).stdout.strip())

    if not banco.exists():
        print(f"Acervo não encontrado em {banco}. Rode montar.py.",
              file=sys.stderr)
        return 1

    if CONSTRUCAO.exists():
        shutil.rmtree(CONSTRUCAO)
    servidor = CONSTRUCAO / "server"
    servidor.mkdir(parents=True)

    print("Copiando o servidor…")
    # `autenticacao.py` viaja junto: por stdio ele não é usado, mas o servidor
    # o importa quando MANUAL_URL_PUBLICA está definida, e um pacote que quebra
    # por módulo ausente falha longe da causa.
    for modulo in ("servidor.py", "autenticacao.py"):
        origem = RAIZ / "servidor" / modulo
        if origem.exists():
            shutil.copy2(origem, servidor / modulo)
    (servidor / "main.py").write_text(ENTRADA, encoding="utf-8")

    for versao in VERSOES:
        marca = "py" + versao.replace(".", "")
        print(f"Instalando as dependências para Python {versao}…")
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet",
             "--target", str(servidor / "lib" / marca),
             "--python-version", versao, "--only-binary=:all:", "mcp>=1.28,<2"],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print(f"  aviso: sem pacotes para {versao}, seguindo sem ela.")
            shutil.rmtree(servidor / "lib" / marca, ignore_errors=True)

    disponiveis = sorted(p.name for p in (servidor / "lib").glob("py*"))
    if not disponiveis:
        print("Nenhuma dependência empacotada.", file=sys.stderr)
        return 1
    print("  versões no pacote:", ", ".join(disponiveis))

    print("Copiando o acervo…")
    (CONSTRUCAO / "dados").mkdir()
    shutil.copy2(banco, CONSTRUCAO / "dados" / "manual_tcu.sqlite3")

    (CONSTRUCAO / "manifest.json").write_text(
        json.dumps(MANIFESTO, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Validando o manifesto…")
    if not validar(CONSTRUCAO):
        print("\nManifesto inválido; nada foi empacotado.", file=sys.stderr)
        return 1

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.unlink(missing_ok=True)
    print("Compactando…")
    with zipfile.ZipFile(DESTINO, "w", zipfile.ZIP_DEFLATED) as pacote:
        for caminho in sorted(CONSTRUCAO.rglob("*")):
            if caminho.is_file() and "__pycache__" not in caminho.parts:
                pacote.write(caminho, caminho.relative_to(CONSTRUCAO))

    print(f"\n{DESTINO}  ({DESTINO.stat().st_size / 1024 / 1024:.1f} MB)")
    print("Instale arrastando o arquivo para Configuracoes > Extensoes do Claude.")
    return 0


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(prog="python empacotar_mcpb.py",
                                description="Empacota o manual do TCU como extensão do Claude.")
    # O banco servido mora no disco rápido: `dados/` é junção para o HD
    # externo, e ler FTS5 de USB custa 1,49 s por busca contra 0,004 s.
    p.add_argument("--banco",
                   default=str(RAIZ / "manual_tcu.sqlite3"),
                   help="banco a empacotar (padrão: o do próprio projeto)")
    # O padrão era deixar `"command": "python"` no manifesto, e isso depende do
    # PATH de quem SOBE o servidor — o Claude Desktop, não o terminal onde se
    # empacotou. Aqui `python` só resolve pelo atalho da Loja em `WindowsApps`,
    # que não está garantido no ambiente do aplicativo: a extensão instalaria e
    # não abriria. Fixar este interpretador é o comportamento certo; `sem_espacos`
    # cuida do 8.3, e `conferir_interpretador` recusa o que não sobe.
    p.add_argument("--python", metavar="EXE", default=sys.executable,
                   help="interpretador gravado no manifesto (padrão: o que está "
                        "rodando este script)")
    args = p.parse_args()
    raise SystemExit(empacotar(Path(args.banco), args.python))
