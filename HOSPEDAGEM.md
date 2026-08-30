# Hospedagem no Render

Repositório: <https://github.com/fm85gn2y4q-maker/manual-tcu-licitacoes>

O acervo (5,0 MB) viaja dentro do repositório, em
`acervo/manual-tcu-v1.0.0.db.gz`, com o sha256 declarado no `Dockerfile` e
conferido **antes** de descomprimir. Não há download em tempo de construção e
não há variável de ambiente a preencher para os dados — a construção se vira
sozinha.

## 1. Aplicar o blueprint

No Render: **Dashboard → Blueprints → New Blueprint Instance**, apontando para
o repositório. Ele lê o `render.yaml` e cria um serviço web Docker no plano
gratuito, chamado `manual-tcu-licitacoes`.

O primeiro build leva alguns minutos: instala o `mcp`, copia o servidor e
descomprime o acervo.

**O primeiro deploy vai subir e não responder a ninguém de fora.** Isso é
esperado — falta a etapa 2.

## 2. As três variáveis, depois que o endereço existir

Só depois do primeiro deploy o Render atribui o endereço público. Anote-o
(algo como `manual-tcu-licitacoes.onrender.com`) e vá em
**Environment → Environment Variables**:

| variável | valor | por quê |
|---|---|---|
| `MANUAL_DOMINIOS` | `manual-tcu-licitacoes.onrender.com` | Sem `https://` e sem barra final. Sem ela o servidor responde **421** a tudo que vem de fora. É a proteção contra DNS rebinding do SDK, e a comparação de Host é **exata — não há curinga**. |
| `MANUAL_URL_PUBLICA` | `https://manual-tcu-licitacoes.onrender.com` | Com `https://`. Liga o fluxo OAuth, que o **ChatGPT exige** para aceitar um conector. O Claude conecta sem ela. |
| `MANUAL_SEGREDO_OAUTH` | gerado pelo blueprint | Confira que existe. Criando o serviço à mão em vez de por blueprint, defina-a: sem ela cada hibernação do plano gratuito invalida as autorizações, e o conector pede autorização o dia inteiro. |

Salvar dispara novo deploy. É esse que fica utilizável.

## 3. Conferir

O endpoint é `https://<host>/mcp`.

```bash
curl -i https://manual-tcu-licitacoes.onrender.com/mcp
```

Resposta esperada: **406 Not Acceptable**, com a mensagem
`Client must accept text/event-stream`. Isso é sinal de saúde — quer dizer que
o servidor está de pé e recusando um GET simples, como deve.

- **404** → o serviço subiu mas a rota não é essa.
- **421 Misdirected Request** → `MANUAL_DOMINIOS` está errada ou ausente.
- **502 / demora de ~50 s** → hibernação do plano gratuito. Normal na primeira
  chamada depois de um tempo parado.

Por isso `healthCheckPath` fica **fora** do `render.yaml`, de propósito: o
Render só considera saudável um GET com 2xx/3xx, e aqui nenhum caminho devolve
isso (`GET /mcp` → 406, `GET /` → 404). Declará-lo deixaria o serviço
eternamente "unhealthy" e o deploy falharia sem dizer por quê.

## 4. Ligar no ChatGPT

Configurações → Conectores → Criar. URL: `https://<host>/mcp`.

O ChatGPT procura os metadados de OAuth antes de falar com o servidor e desiste
se não os achar ("does not implement OAuth") — daí a `MANUAL_URL_PUBLICA`.

A aprovação do fluxo é **automática**: quem chegar à URL completa o fluxo e
recebe token. Isso protege contra chamada sem token, não contra quem conhece o
endereço. É aceitável aqui, porque o manual é publicação de acesso aberto do
TCU; não seria para acervo de obra protegida ou com dado pessoal.

## 5. Ligar no Claude

O Claude conecta a um servidor MCP sem autenticação, então a URL `/mcp` basta.

Para uso local, sem depender de rede nem de hospedagem, o melhor caminho é a
extensão: `dist/manual-tcu-licitacoes.mcpb`, arrastada para
**Configurações → Extensões**. Roda por stdio, com o acervo dentro do pacote.

## Publicar edição nova

Quando o TCU publicar a 6ª edição:

```bash
.venv/Scripts/python.exe coletar.py      # recoleta os posts
.venv/Scripts/python.exe montar.py       # remonta o banco
.venv/Scripts/python.exe conferir.py     # e confere contra as fontes
```

Depois, gerar o `.gz` novo em `acervo/`, trocar as duas linhas `ARG ACERVO` e
`ARG ACERVO_SHA256` do `Dockerfile`, e commitar. O Render reconstrói ao receber
o push. Se o hash não bater, a construção falha — que é o comportamento
desejado: melhor falhar do que servir um acervo diferente do que foi testado.
