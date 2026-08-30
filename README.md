# Manual TCU — Licitações e Contratos

Servidor MCP sobre o manual **"Licitações & Contratos: Orientações e
Jurisprudência do TCU"**, 5ª edição (Tribunal de Contas da União, 2025),
na íntegra.

| | |
|---|---|
| Seções | 210 (capítulos 1 a 6, até o nível 5.10.2.19) |
| Parágrafos e itens | 3.094 |
| Quadros | 484 |
| Linhas de quadro | 3.138 |
| Julgados citados | 1.161 — 835 acórdãos distintos e 19 súmulas, de 1996 a 2025 |
| Notas de rodapé | 1.513 |
| Páginas do PDF | 1.042 (1.031 impressas) |
| Referências bibliográficas | 95 |
| Banco | 17,8 MB · 5,0 MB comprimido |

Os quadros se distribuem assim, e é essa distribuição que dá as ferramentas:

| categoria | quadros | linhas |
|---|---|---|
| Referências normativas | 158 | 1.005 |
| Jurisprudência do TCU | 151 | 1.422 |
| Riscos relacionados | 115 | 508 |
| Modelos | 41 | 140 |
| Figuras (diagramas, sem texto) | 12 | — |
| Outros | 7 | 63 |

## O achado que governa o desenho

**74% dos julgados que o manual cita são anteriores à Lei 14.133/2021.**
Medido: 860 de 1.161 foram julgados antes de 2021, sob a Lei 8.666/1993; 269
são de 2021 em diante. O manual os traz por entender que a tese sobrevive à
mudança de lei — mas isso é opinião do manual, e **nada no enunciado avisa sob
qual lei ele foi firmado**. Todo julgado anterior a 2021 sai daqui com aviso.

E há um segundo risco, de outra natureza: a mesma seção reúne cinco coisas de
autoridade diferente com o mesmo peso visual — a prosa do manual (orientação,
não decisão), o enunciado de acórdão (o que o Tribunal firmou), o texto de lei
transcrito, os riscos (elaboração própria) e os modelos. Todo resultado traz
`natureza` dizendo qual é. Entre as linhas dos quadros de jurisprudência, 150
não são julgado nenhum: dizem "Pesquisa de Jurisprudência" e são sugestão de
busca no portal do TCU. Elas nunca aparecem como julgado neste acervo.

## Por que o texto não vem do PDF

O PDF publicado pelo TCU **não tem camada de texto no corpo de 91 páginas**.
O manual foi diagramado no Word 2016 e blocos inteiros de prosa foram colados
como imagem. Medido: a página 149 impressa — a lista dos princípios do art. 5º
da Lei 14.133/2021 — tem 691 caracteres de texto, todos de título e rodapé;
a lista inteira é imagem. Ao todo, 156 páginas têm 10% ou mais da mancha em
imagem, e a cópia anterior do arquivo tem exatamente a mesma falha, o que
mostra que a rasterização está na origem, não na compressão.

Por isso o texto de registro vem da **versão interativa** que o TCU publica em
<https://licitacoesecontratos.tcu.gov.br/> — 211 posts pela API REST do
WordPress, com texto nativo, quadros em tabela e notas de rodapé ancoradas.

O PDF continua no acervo, e entra por três coisas que o HTML não tem:

1. a **página impressa** de cada seção, que é o que se cita (offset 11 entre a
   página do PDF e a impressa, conferido nas páginas 62 e 160);
2. a **Lista de quadros**, que dá a página de 468 dos 484 quadros;
3. as **Referências bibliográficas**.

`ler_pagina` devolve o texto do PDF e avisa quando a página está rasterizada.

## Ferramentas

| | |
|---|---|
| `pesquisar_orientacao` | na prosa — o que o TCU ensina a fazer |
| `pesquisar_jurisprudencia` | nos enunciados — o que o Tribunal decidiu; filtra por regime |
| `ler_secao` | uma seção inteira: prosa, quadros e notas |
| `sumario` | o sumário, com a página impressa de cada item |
| `riscos_de` | os 508 riscos, por seção ou por assunto |
| `modelos_e_checklists` | os 140 modelos indicados |
| `referencias_normativas` | os 1.005 dispositivos transcritos |
| `julgado_no_manual` | a pergunta inversa: o manual usa este acórdão, e para quê? |
| `ler_pagina` | o texto de uma página do PDF, pela numeração impressa |
| `cobertura_do_acervo` | volumes, período e limites |
| `pontos_cegos` | onde a busca não enxerga |
| `search` / `fetch` | compatibilidade com a pesquisa profunda do ChatGPT |

Nenhum julgado tem link para inteiro teor: o portal do TCU não publica
permalink. O que existe é `url_busca_no_tcu`, uma consulta montada por número e
ano — mais confiável que o link do próprio manual, que em 675 dos 1.161 casos é
busca por texto livre.

## Como se monta

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe coletar.py        # 211 posts da API do TCU
.venv/Scripts/python.exe medir.py          # camada de texto e sumário do PDF
.venv/Scripts/python.exe medir_imagens.py  # quanto do corpo está em imagem
.venv/Scripts/python.exe montar.py         # o banco
.venv/Scripts/python.exe conferir.py       # 25 conferências contra as fontes
```

`bruto/` fica fora do Git: são o PDF de 35 MB e o JSON cru da API, ambos
recuperáveis das fontes. O que viaja no repositório é
`acervo/manual-tcu-v1.0.0.db.gz` (5,0 MB), com o sha256 declarado no
`Dockerfile` e conferido antes de descomprimir.

## Como se testa

```bash
.venv/Scripts/python.exe conferir.py            # o banco contra as fontes
.venv/Scripts/python.exe servidor/testar.py     # as 13 ferramentas
.venv/Scripts/python.exe conferir_pacote.py     # o .mcpb recém-construído, por stdio
.venv/Scripts/python.exe conferir_instalado.py  # a extensão JÁ INSTALADA no Claude
```

`conferir_pacote.py` mantém o canal aberto de propósito: despejando os pedidos
de uma vez e fechando a entrada, o servidor vê EOF e encerra **antes** de
escrever a última resposta — cinco pedidos processados, quatro respostas.

## Claude Desktop

```bash
.venv/Scripts/python.exe empacotar_mcpb.py --python <caminho do python.exe>
```

Gera `dist/manual-tcu-licitacoes.mcpb` (49,3 MB), que se instala arrastando
para Configurações → Extensões. O pacote leva as dependências para Python 3.12,
3.13 e 3.14, e o acervo inteiro: roda local, por stdio, sem conta e sem rede.

Fixar o interpretador com `--python` não é opcional na prática: sem isso o
manifesto fica com `"command": "python"`, que depende do PATH de quem sobe o
servidor — o Claude Desktop, não o terminal onde se empacotou.

Aponte para o **Python da Store** (`AppData\Local\Microsoft\WindowsAppsPythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\python.exe`), não para o
venv do projeto: o pacote leva as próprias dependências em `server/lib/py312`,
inseridas à frente do `sys.path`, então não precisa do venv — e apontar para
ele faria a extensão morrer se a pasta do projeto fosse movida. É a convenção
que o `acervo-cnj` instalado já segue.

## Render

`render.yaml` é blueprint pronto. Depois do primeiro deploy, quando o endereço
público existir, definir:

| variável | para quê |
|---|---|
| `MANUAL_DOMINIOS` | o host público, sem `https://`. Sem ele o servidor responde **421** a tudo que vem de fora — é proteção contra DNS rebinding, e a comparação de Host é exata, sem curinga. |
| `MANUAL_URL_PUBLICA` | ativa o fluxo OAuth, que o ChatGPT exige para aceitar um conector. O Claude conecta sem. |
| `MANUAL_SEGREDO_OAUTH` | gerado pelo blueprint. Sem ele, cada hibernação do plano gratuito invalida as autorizações e o conector pede autorização o dia inteiro. |

`healthCheckPath` fica fora de propósito: não há caminho que responda 2xx a um
GET (o endpoint MCP devolve 406 a `GET /mcp` e 404 a `GET /`), e declará-lo
deixaria o serviço eternamente "unhealthy".

O endpoint é `https://<host>/mcp`.

## Licença do conteúdo

O TCU declara na ficha catalográfica: *"Permite-se a reprodução desta
publicação, em parte ou no todo, sem alteração do conteúdo, desde que citada a
fonte e sem fins comerciais."* O acervo preserva o texto sem alteração e cita a
fonte em cada resultado. O uso comercial não está autorizado pelo Tribunal.

O código é de Matheus Menegatti.
