"""Instala o acervo comprimido no lugar onde o servidor o procura.

Aceita as duas origens, porque o projeto usa uma e mantém a outra pronta:

    python instalar_acervo.py acervo/acervo-cnj-v1.0.0.db.gz \
        dados/cnj.sqlite <sha256>          # arquivo do próprio repositório
    python instalar_acervo.py https://…/x.db.gz dados/cnj.sqlite <sha256>

Em qualquer das duas, o sha256 é conferido **antes** de descomprimir. É o que
fecha a cadeia `versão fixa → hash declarado → conferência no build → falha
fechada`: divergindo o arquivo, a construção para em vez de subir um acervo
diferente daquele que foi testado.
"""

from __future__ import annotations

import gzip
import hashlib
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

BLOCO = 4 * 1024 * 1024


def _resumo(caminho: Path) -> str:
    """Hash em blocos: o arquivo tem dezenas de MB e não precisa ir todo à memória."""
    digestor = hashlib.sha256()
    with caminho.open("rb") as fluxo:
        for bloco in iter(lambda: fluxo.read(BLOCO), b""):
            digestor.update(bloco)
    return digestor.hexdigest()


def instalar(origem: str, destino: Path, esperado: str | None = None) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)

    local = Path(origem)
    if local.is_file():
        comprimido, temporario = local, False
        print(f"Usando {local} ({local.stat().st_size / 1048576:.1f} MB)",
              file=sys.stderr)
    else:
        print(f"Baixando {origem}", file=sys.stderr)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gz") as arquivo:
            comprimido = Path(arquivo.name)
        temporario = True
        # Asset de release em repositório PRIVADO devolve 404 ao download
        # anônimo — medido, não suposto. Havendo token, a requisição vai pela
        # API com `Accept: application/octet-stream`, que é a única forma de
        # baixar o binário de um asset privado.
        cabecalhos = {"User-Agent": "instalar-acervo"}
        token = os.environ.get("GITHUB_TOKEN", "").strip()
        if token:
            cabecalhos["Authorization"] = f"token {token}"
            cabecalhos["Accept"] = "application/octet-stream"
            print("  usando GITHUB_TOKEN", file=sys.stderr)
        pedido = urllib.request.Request(origem, headers=cabecalhos)
        try:
            with urllib.request.urlopen(pedido, timeout=600) as resposta:
                with comprimido.open("wb") as saida:
                    shutil.copyfileobj(resposta, saida, length=BLOCO)
        except urllib.error.HTTPError as erro:
            if erro.code == 404 and not token:
                raise SystemExit(
                    "404 no download do acervo.\n"
                    "  Asset de release em repositório privado não abre sem "
                    "credencial.\n"
                    "  Ou o repositório passa a público, ou defina GITHUB_TOKEN "
                    "na construção\n  e use a URL da API do asset "
                    "(.../releases/assets/ID), não a de download direto."
                ) from erro
            raise

    try:
        if esperado:
            obtido = _resumo(comprimido)
            if obtido != esperado:
                raise SystemExit(
                    f"Conferência falhou.\n  esperado: {esperado}\n  obtido:   {obtido}"
                )
            print("Integridade conferida.", file=sys.stderr)

        with gzip.open(comprimido, "rb") as entrada, destino.open("wb") as saida:
            shutil.copyfileobj(entrada, saida, length=BLOCO)
    finally:
        if temporario:
            comprimido.unlink(missing_ok=True)

    print(f"Acervo em {destino} ({destino.stat().st_size / 1048576:.1f} MB)",
          file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    instalar(sys.argv[1], Path(sys.argv[2]),
             sys.argv[3] if len(sys.argv) > 3 else None)
