# Imagem do servidor do manual do TCU (Render, Cloud Run, Fly e afins).
FROM python:3.12-slim

WORKDIR /app

# As dependências mudam menos que o código: instaladas antes, para aproveitar o
# cache entre construções.
COPY requirements-servidor.txt ./
RUN pip install --no-cache-dir -r requirements-servidor.txt

COPY servidor/ ./servidor/

# O acervo viaja no repositório, comprimido: 5,0 MB, numa base que se recoleta
# quando o TCU publicar nova edição. Vindo pelo Git somem três modos de falha
# que o asset de release trazia — repositório privado devolvendo 404 no download
# anônimo, asset errado anexado, URL divergente do nome do repositório — além da
# dependência de rede no build.
#
# O que não muda é a cadeia de integridade: o sha256 é declarado aqui e
# conferido ANTES de descomprimir. Divergindo o arquivo, a construção falha em
# vez de subir um acervo diferente daquele que foi testado. Publicar acervo novo
# é trocar estas duas linhas e commitar o novo .gz.
#
# v1.0.0: 210 seções, 484 quadros, 1.161 julgados, 1.513 notas de rodapé, e as
# 1.042 páginas do PDF. Texto vindo da versão interativa do TCU, porque no PDF
# publicado o corpo de 91 páginas foi colado como imagem.
ARG ACERVO=acervo/manual-tcu-v1.0.0.db.gz
ARG ACERVO_SHA256=a290976c5cbda938d6b2664ba927041d832f85521e704defb7dd016333e80ea4
COPY instalar_acervo.py ./
COPY acervo/ ./acervo/
RUN python instalar_acervo.py "$ACERVO" dados/manual_tcu.sqlite3 "$ACERVO_SHA256" \
    && rm -rf acervo/

# O serviço define a porta; 8080 é o padrão do Cloud Run quando ele não define.
ENV PORT=8080 \
    MANUAL_HOST=0.0.0.0 \
    MANUAL_BANCO=/app/dados/manual_tcu.sqlite3 \
    PYTHONUTF8=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8080

# MANUAL_DOMINIOS é definido depois do primeiro deploy, quando o endereço
# público passa a existir. Sem ele o servidor responde 421 a tudo que vem de
# fora — é a proteção contra DNS rebinding, e a comparação de Host é exata,
# sem curinga.
CMD ["python", "servidor/servidor.py", "http"]
