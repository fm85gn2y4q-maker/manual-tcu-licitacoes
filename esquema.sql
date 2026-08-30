PRAGMA journal_mode = WAL;

CREATE TABLE obra (
  id             INTEGER PRIMARY KEY,
  titulo         TEXT NOT NULL,
  edicao         TEXT,
  ano            INTEGER,
  orgao          TEXT,
  url_site       TEXT,
  url_pdf        TEXT,
  sha256_pdf     TEXT,
  paginas_pdf    INTEGER,
  offset_pagina  INTEGER,   -- pagina_impressa = pagina_pdf - offset
  coletado_em    TEXT NOT NULL
);

-- Uma secao numerada do manual (1.1 ate 6.4.3.4).
CREATE TABLE secao (
  id              INTEGER PRIMARY KEY,
  numero          TEXT NOT NULL,      -- "3.4.1"
  titulo          TEXT NOT NULL,
  nivel           INTEGER NOT NULL,
  numero_pai      TEXT,
  capitulo        TEXT NOT NULL,
  slug            TEXT NOT NULL,
  url             TEXT NOT NULL,
  ordem           INTEGER NOT NULL,
  pagina_pdf      INTEGER,
  pagina_impressa INTEGER,
  wp_id           INTEGER,
  wp_modified     TEXT,
  texto           TEXT NOT NULL,      -- prosa da secao, sem os quadros
  chars           INTEGER NOT NULL
);
CREATE UNIQUE INDEX ix_secao_numero ON secao(numero);
CREATE INDEX ix_secao_ordem ON secao(ordem);

-- Bloco de texto corrido, na ordem em que aparece.
CREATE TABLE bloco (
  id        INTEGER PRIMARY KEY,
  secao_id  INTEGER NOT NULL REFERENCES secao(id),
  ordem     INTEGER NOT NULL,
  tipo      TEXT NOT NULL,            -- prosa | item | subtitulo
  texto     TEXT NOT NULL
);
CREATE INDEX ix_bloco_secao ON bloco(secao_id, ordem);

-- Quadro/Figura/Tabela numerado do manual.
CREATE TABLE quadro (
  id              INTEGER PRIMARY KEY,
  secao_id        INTEGER NOT NULL REFERENCES secao(id),
  especie         TEXT NOT NULL,      -- Quadro | Figura | Tabela
  numero          INTEGER,
  titulo          TEXT NOT NULL,
  categoria       TEXT NOT NULL,      -- jurisprudencia | riscos | modelos |
                                      -- referencias_normativas | figura | outro
  fonte           TEXT,               -- a linha "Fonte: ..." do manual
  ordem           INTEGER NOT NULL,
  n_linhas        INTEGER NOT NULL,
  so_imagem       INTEGER NOT NULL DEFAULT 0,
  pagina_impressa INTEGER
);
CREATE INDEX ix_quadro_secao ON quadro(secao_id, ordem);
CREATE INDEX ix_quadro_cat ON quadro(categoria);
CREATE INDEX ix_quadro_num ON quadro(especie, numero);

-- Linha de um quadro. `rotulo` e a 1a coluna; `conteudo`, o resto.
CREATE TABLE linha (
  id           INTEGER PRIMARY KEY,
  quadro_id    INTEGER NOT NULL REFERENCES quadro(id),
  ordem        INTEGER NOT NULL,
  rotulo       TEXT,
  conteudo     TEXT NOT NULL,
  url_rotulo   TEXT,
  n_colunas    INTEGER NOT NULL,
  colunas_json TEXT NOT NULL,
  -- A 1a linha de todo quadro e o cabecalho da tabela, e nao conteudo.
  -- Medido: 115/115 quadros de risco comecam por "Riscos" (mediana de 6
  -- caracteres contra 376 das linhas reais) e 158/158 de referencias por
  -- "Dispositivos". Sem esta marca, "Riscos" aparece como se fosse um risco.
  cabecalho    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX ix_linha_quadro ON linha(quadro_id, ordem);
CREATE INDEX ix_linha_cab ON linha(cabecalho);

-- Julgado extraido do rotulo de uma linha de quadro de jurisprudencia.
-- Linha "Pesquisa de Jurisprudencia" NAO gera registro aqui: nao e julgado.
CREATE TABLE julgado (
  id                 INTEGER PRIMARY KEY,
  linha_id           INTEGER NOT NULL REFERENCES linha(id),
  secao_id           INTEGER NOT NULL REFERENCES secao(id),
  especie            TEXT NOT NULL,   -- acordao | sumula | decisao
  numero             TEXT NOT NULL,
  ano                INTEGER,
  colegiado          TEXT,
  citacao            TEXT NOT NULL,
  rotulo_original    TEXT NOT NULL,
  enunciado          TEXT NOT NULL,
  url                TEXT,
  anterior_a_14133   INTEGER          -- 1 se ano < 2021; NULL se ano ausente
);
CREATE INDEX ix_julgado_num ON julgado(numero, ano);
CREATE INDEX ix_julgado_secao ON julgado(secao_id);
CREATE INDEX ix_julgado_ano ON julgado(ano);

CREATE TABLE nota (
  id       INTEGER PRIMARY KEY,
  secao_id INTEGER NOT NULL REFERENCES secao(id),
  numero   INTEGER NOT NULL,
  texto    TEXT NOT NULL
);
CREATE INDEX ix_nota_secao ON nota(secao_id, numero);

-- Camada do PDF: existe para dar a pagina que se cita e para conferir o HTML.
CREATE TABLE pagina (
  pagina_pdf      INTEGER PRIMARY KEY,
  pagina_impressa INTEGER,
  texto           TEXT NOT NULL,
  chars           INTEGER NOT NULL,
  area_imagem_pct REAL NOT NULL,
  rasterizada     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE referencia (
  id     INTEGER PRIMARY KEY,
  ordem  INTEGER NOT NULL,
  texto  TEXT NOT NULL
);

CREATE TABLE nota_de_coleta (
  chave TEXT PRIMARY KEY,
  valor TEXT NOT NULL
);

CREATE VIRTUAL TABLE fts_secao USING fts5(
  titulo, texto,
  content='secao', content_rowid='id',
  tokenize="unicode61 remove_diacritics 2"
);
CREATE VIRTUAL TABLE fts_julgado USING fts5(
  citacao, enunciado,
  content='julgado', content_rowid='id',
  tokenize="unicode61 remove_diacritics 2"
);
CREATE VIRTUAL TABLE fts_linha USING fts5(
  rotulo, conteudo,
  content='linha', content_rowid='id',
  tokenize="unicode61 remove_diacritics 2"
);
CREATE VIRTUAL TABLE fts_pagina USING fts5(
  texto,
  content='pagina', content_rowid='pagina_pdf',
  tokenize="unicode61 remove_diacritics 2"
);
