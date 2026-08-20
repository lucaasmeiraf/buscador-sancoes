# Guia de configuração — Buscador de Sanções

Passo a passo completo para deixar a automação pronta para rodar: credenciais,
variáveis de ambiente, teste local e agendamento no Claude (Routines).

> Visão geral do que a automação faz: ver [README.md](../README.md).
> Passo a passo que o agente executa a cada run: ver [SKILL.md](../SKILL.md).

---

## 1. Pré-requisitos

| Item | Para quê | Onde obter |
|---|---|---|
| Conta no INLABS | Baixar o DOU em XML | Cadastro gratuito em <https://inlabs.in.gov.br> |
| Servidor Evolution API | Enviar WhatsApp | Servidor próprio em nuvem (VPS, ex.: <https://www.hostinger.com/br/servidor-vps>) com [EasyPanel](https://easypanel.io) e [Evolution API v2](https://docs.evolutionfoundation.com.br) instalados |
| Repositório no GitHub | O Routines clona o repo a cada execução | Este repositório publicado no GitHub (conta em <https://github.com/signup>) |
| Python 3.11+ | Rodar os scripts (só para teste local) | <https://www.python.org/downloads/> |
| Assinatura Claude Pro (ou superior) | Agendar a rotina no Routines | <https://claude.com/pricing> |

## 2. Credenciais e variáveis de ambiente

A automação lê **tudo** de variáveis de ambiente — nenhum segredo fica no código
ou no repositório. Os nomes estão em [`.env.example`](../.env.example):

| Variável | Conteúdo |
|---|---|
| `INLABS_LOGIN` | E-mail do cadastro no INLABS |
| `INLABS_SENHA` | Senha do cadastro no INLABS |
| `EVOLUTION_API_URL` | URL base do servidor Evolution API, sem barra final (ex.: `https://evo.seudominio.com`) |
| `EVOLUTION_API_KEY` | API key da instância (gerada no servidor Evolution) |
| `EVOLUTION_INSTANCE` | Nome da instância criada no servidor |
| `WHATSAPP_DESTINO` | Número da advogada (cliente) — **só recebe leads**. Formato internacional só dígitos (ex.: `5561999998888`) |
| `WHATSAPP_ADMIN` | **Opcional.** Número do operador da automação — recebe os **alertas técnicos** (fonte bloqueada, push falhou). Sem ela os alertas ficam só no log da run; nunca são redirecionados para a cliente. |
| `PORTAL_TRANSPARENCIA_TOKEN` | **Opcional.** Chave da API do Portal da Transparência (CEIS/CNEP). Sem ela a rotina roda igual, só entrega o lead sem CNPJ do cadastro e sem link do registro de sanção. |

### 2.1 INLABS (Imprensa Nacional)

1. Acesse <https://inlabs.in.gov.br> e faça o cadastro (gratuito).
2. Confirme o e-mail e guarde login/senha — são os valores de `INLABS_LOGIN` e
   `INLABS_SENHA`.
3. Teste no navegador: logado, deve ser possível baixar os zips do dia
   (`AAAA-MM-DD-DO1.zip` etc.).

### 2.2 Portal da Transparência (CEIS/CNEP) — opcional

1. Peça a chave em
   <https://portaldatransparencia.gov.br/api-de-dados/cadastrar-email> (gratuita,
   chega por e-mail).
2. Guarde o valor em `PORTAL_TRANSPARENCIA_TOKEN`.
3. Acrescente `api.portaldatransparencia.gov.br` à allowlist do ambiente (§4.3).

A API autentica por **header**, não por query string: cada requisição leva
`chave-api-dados: <token>` — a mesma coisa que a documentação do Portal descreve
como `[{"key": "chave-api-dados", "value": "<token>"}]`. Isso já está
implementado em [`scripts/enriquecer_sancoes.py`](../scripts/enriquecer_sancoes.py);
a env var guarda **só o valor da chave**, sem o nome do header e sem aspas.

Teste rápido da chave (substitua o CNPJ por qualquer um):

```bash
curl -H "chave-api-dados: $PORTAL_TRANSPARENCIA_TOKEN" \
  "https://api.portaldatransparencia.gov.br/api-de-dados/ceis?pagina=1"
```

`401`/`403` = chave inválida ou ausente; `429` = limite por minuto estourado (o
script já espera e repete nesse caso).

Sem essa chave a rotina funciona normalmente — o `enriquecer_sancoes.py` avisa e
segue. O que se perde: CNPJ quando o diário não traz, o link do registro de
sanção e o histórico de sanções anteriores da empresa.

### 2.3 Evolution API (WhatsApp)

1. No seu servidor Evolution API, crie uma instância (ex.: `buscador-sancoes`) e
   anote a **API key**.
2. Conecte a instância a um número de WhatsApp (QR code no painel da Evolution).
   Recomendação: usar um número dedicado da automação, não o pessoal.
3. Teste manual do endpoint (substitua os valores):

   ```bash
   curl -X POST "https://SEU_SERVIDOR/message/sendText/SUA_INSTANCIA" \
     -H "apikey: SUA_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"number": "5561999998888", "text": "teste buscador-sancoes"}'
   ```

   Se a mensagem chegar no WhatsApp de destino, os quatro valores `EVOLUTION_*`
   e `WHATSAPP_DESTINO` estão corretos.

## 3. Teste local (opcional, recomendado antes de agendar)

```bash
# 1. dependências
pip install -r requirements.txt

# 2. variáveis de ambiente (copie o modelo e preencha — o .env NÃO é commitado)
cp .env.example .env
# preencha o .env e exporte (ou use um loader de sua preferência)

# 3. pipeline determinístico
python scripts/coleta_inlabs.py     # baixa o DOU do dia -> data/raw/dou/
python scripts/coleta_dodf.py       # baixa o DODF do dia -> data/raw/dodf/
python scripts/prefiltro.py         # seleciona trechos -> data/candidatos.json

# 3b. só o lado do GitHub Actions (o que o workflow publica na branch de dados)
python scripts/prefiltro.py --fonte dodf --exportar data/dodf/$(date +%F)/blocos.json

# 4. teste de envio
python scripts/enviar_whatsapp.py --texto "teste do buscador de sanções"
```

O `prefiltro` informa quantos candidatos saíram **com link direto da matéria**.
Se esse número vier zerado num dia com candidatos do DOU, o índice do
`www.in.gov.br` não foi baixado (rede bloqueada ou layout do site mudou) — os
links caem para a página impressa, que continua correta. Diagnóstico isolado:

```bash
python scripts/links_dou.py 2026-08-07 do3   # deve imprimir milhares de chaves
```

Os endpoints do INLABS e do DODF foram conferidos em 09/08/2026; se um deles
mudar, os erros aparecem já no passo 3.

A extração em si (LLM) não roda localmente por script: é o agente Claude que,
seguindo `SKILL.md` e `prompts/rotina_sancoes.md`, processa `data/candidatos.json`.
Para simular, cole os candidatos em uma conversa do Claude junto com o prompt.

## 4. Agendamento no Claude (Routines)

Routines são agentes em nuvem que rodam em horário agendado (cron), clonando o
repositório do GitHub a cada execução. Disponível nos planos **Pro, Max, Team e
Enterprise**, com Claude Code na web habilitado.

### 4.1 Pré-requisito: repositório no GitHub conectado

1. Publique este repositório no GitHub (`git push`).
2. Conecte sua conta GitHub ao Claude Code na web/desktop (autorização OAuth —
   no CLI, o comando `/web-setup` guia a conexão).
3. Observação: os commits feitos pela rotina (ex.: atualização de
   `data/vistos.json`) aparecem no GitHub **como o seu usuário**.

### 4.2 Criar a rotina — três caminhos equivalentes

Tudo sincroniza na mesma conta; a rotina criada em um lugar aparece nos outros.

**A) App Claude Desktop (Mac/Windows):**

1. Abra o app Claude Desktop e entre na área do **Claude Code**.
2. Na barra lateral, clique em **Routines** → **New routine**.
3. Escolha **Cloud** (não "Local" — é a nuvem que clona o repo sozinha).
4. Preencha o formulário:
   - **Nome**: `Buscador de Sanções`
   - **Repositório**: selecione este repo no GitHub
   - **Environment**: o ambiente de nuvem com as env vars (ver 4.3)
   - **Trigger**: diário, em dias úteis, por volta das **8h (horário de Brasília)**
     — o horário é interpretado no seu fuso local
   - **Prompt** da rotina (ver 4.4)
5. Clique em **Create**.

**B) Web:** <https://claude.ai/code/routines> → **New routine** → mesmo formulário.

**C) CLI (terminal):** rode `/schedule` dentro do Claude Code e responda ao fluxo
de perguntas (nome, repo, horário, prompt). `/schedule list`, `/schedule update` e
`/schedule run` gerenciam as rotinas existentes.

### 4.3 Environment do Routines: env vars e rede

As variáveis da seção 2 vão no **cloud environment** usado pela rotina:

1. Em <https://claude.ai/code>, abra o seletor de ambiente (ícone de nuvem) →
   engrenagem do ambiente → **Update cloud environment**.
2. No campo de variáveis, cole no formato `.env` (uma por linha):

   ```
   INLABS_LOGIN=...
   INLABS_SENHA=...
   EVOLUTION_API_URL=...
   EVOLUTION_API_KEY=...
   EVOLUTION_INSTANCE=...
   WHATSAPP_DESTINO=...
   WHATSAPP_ADMIN=...
   PORTAL_TRANSPARENCIA_TOKEN=...
   DODF_BASE_URL=...
   TZ=America/Sao_Paulo
   ```

   `DODF_BASE_URL` é o relay do DODF no VPS (§4.6) — na nuvem ela é necessária,
   porque o firewall do GDF derruba conexões diretas da VM (`docs/ISSUES.md`
   §1).

   São as mesmas da seção 2 (a lista canônica de nomes está em
   [`.env.example`](../.env.example)); `PORTAL_TRANSPARENCIA_TOKEN` e
   `WHATSAPP_ADMIN` são as únicas opcionais — sem a primeira a rotina roda sem o
   enriquecimento CEIS/CNEP; sem a segunda os alertas técnicos ficam só no log
   (leads para a cliente em `WHATSAPP_DESTINO`, alertas técnicos para o operador
   em `WHATSAPP_ADMIN` — nunca misturar).
   `TZ` não é segredo: a VM da nuvem roda em
   UTC e os scripts usam a data local (`date.today()`), então sem ela uma
   execução agendada para depois das 21h de Brasília buscaria o diário do dia
   seguinte. Às 8h da manhã a data coincide, mas a variável evita a pegadinha
   caso o horário do trigger mude.

3. **Rede**: o ambiente de nuvem passa por um proxy que bloqueia domínios fora da
   lista padrão. Em **Network access → Custom → Allowed domains**, adicione
   **todos de uma vez, na criação do ambiente** (ver o aviso abaixo):
   - `inlabs.in.gov.br` — download do DOU
   - `www.in.gov.br` — é de lá que `scripts/links_dou.py` tira o link exato de
     cada matéria. Sem esse domínio a rotina ainda funciona, mas cai para o link
     de página (menos preciso — `docs/ISSUES.md` §8).
   - `api.portaldatransparencia.gov.br` — enriquecimento CEIS/CNEP (só se usar a chave)
   - o domínio do seu servidor Evolution API

   `dodf.df.gov.br` na allowlist **não adianta**: o proxy até libera, mas o
   firewall do GDF derruba a conexão vinda da VM (`docs/ISSUES.md` §1). O DODF
   chega pela `DODF_BASE_URL` (relay no domínio da Evolution, já listado acima)
   ou pela branch do GitHub Actions (§4.6).

   > ⚠️ Allowlist liberada **não garante** acesso: o site de destino ainda pode
   > recusar o IP da VM (foi o caso do DODF — e `www.in.gov.br` tem o mesmo
   > sintoma, `docs/ISSUES.md` §8). Antes de culpar a allowlist, rode o
   > diagnóstico abaixo — ele separa as duas assinaturas.
   >
   > Escreva **só o hostname e o nome completo**, sem `https://` e sem barra
   > final. Para conferir de dentro do ambiente:
   >
   > ```bash
   > python scripts/diagnostico_rede.py
   > ```
   >
   > Ele testa cada host e diz, para cada falha, se a causa é a allowlist, o
   > WAF do site ou instabilidade — cada uma com solução diferente.

> ⚠️ **Sobre segredos**: hoje o Claude Code em nuvem **não tem cofre de segredos**
> dedicado — as env vars do ambiente ficam visíveis para quem usa aquele ambiente.
> Em conta individual isso equivale a "visível só para você", mas em conta de
> equipe use um ambiente próprio da rotina e credenciais de escopo mínimo
> (ex.: instância Evolution exclusiva; o cadastro INLABS é gratuito — crie um só
> para a automação).

### 4.4 Script de configuração do ambiente (setup script)

A VM da nuvem já vem com Python 3 e pip, mas **não** com as bibliotecas dos
scripts. No formulário do ambiente de nuvem, em **Setup script** (App Desktop:
"Script de configuração"), coloque:

```bash
python3 -m pip install --break-system-packages --upgrade requests pypdf cryptography || python3 -m pip install --upgrade requests pypdf cryptography
```

O comando é **uma linha só, e o setup script deve conter apenas ela** — apague
linhas antigas ao editar. Dois acidentes já vistos com esse comando:

- quebra de linha no meio (colagem que "enrolou" a linha): o resto do comando
  vira linha própria e o shell tenta executá-lo — falha com
  `requests: command not found` e exit 127 (visto em 13/08/2026);
- a versão antiga com `\` de continuação, que no PowerShell vira argumento
  literal e o pip falha com "Directory '\\' is not installable".

O `--upgrade` não é opcional: sem ele o pip vê a cryptography quebrada do
sistema como "already satisfied" e **não instala nada** (visto na mesma
execução de 13/08/2026).

As dependências (lista canônica em [`requirements.txt`](../requirements.txt)):
`requests` (as três chamadas HTTP: INLABS, DODF, Evolution), `pypdf` (leitura
do PDF do DODF) e `cryptography` — esta última não é usada diretamente: a
imagem da VM traz uma `cryptography` de sistema **quebrada** (binding Rust sem
`_cffi_backend`) que derruba o `import pypdf` com `PanicException` em vez de
`ImportError` (visto em 12/08/2026). A versão do pip fica na frente no
`sys.path` e neutraliza a do sistema.
Todo o resto dos scripts é biblioteca padrão do Python. Os pacotes são nomeados
direto no comando — e não via `-r requirements.txt` — porque o setup script roda
num diretório de trabalho que não é a raiz do repositório, e o caminho relativo
falha com "No such file or directory". O `||` é uma salvaguarda: em imagens
Debian recentes o pip global recusa instalar sem `--break-system-packages`, e em
imagens mais antigas essa flag não existe — a linha funciona nos dois casos.

Dois detalhes de comportamento:

- O setup script roda na **criação/atualização do snapshot** do ambiente, não a
  cada execução. As dependências ficam embutidas na imagem — a rotina começa
  rápida e determinística. Se `requirements.txt` mudar, atualize também a lista
  de pacotes no setup script e re-crie o snapshot do ambiente.
- Durante o setup o PyPI já está liberado por padrão. A allowlist customizada da
  seção 4.3 vale para o **runtime** da rotina, não para a instalação.

Sem esse script, o passo 1 do `SKILL.md` falha no primeiro
`python scripts/coleta_inlabs.py` (`ModuleNotFoundError: requests`) e a rotina
passa a depender de o agente improvisar a instalação a cada execução.

### 4.5 Prompt da rotina

O Routines recebe um prompt a cada execução. Como o `CLAUDE.md` do repositório é
lido automaticamente e já aponta para o `SKILL.md`, o prompt pode ser curto, mas
seja explícito por garantia:

```
Execute a rotina diária do Buscador de Sanções seguindo exatamente o passo a
passo de SKILL.md, na ordem. Só vira lead penalidade com MULTA acima de
R$ 200 mil (ou sem valor expresso) em contrato de infraestrutura rodoviária.
Copie link, edição e página dos candidatos sem alterar — nunca monte URL.
Ao final, envie o resumo por WhatsApp (scripts/enviar_whatsapp.py), atualize a
planilha (scripts/planilha.py) e faça commit+push apenas de data/vistos.json e
data/leads.csv (com o fallback e a verificação do passo 8 do SKILL.md). Se
alguma fonte falhar, siga com a outra; detalhe técnico de falha vai só no
alerta ao operador (enviar_whatsapp.py --admin), nunca na mensagem da cliente.
```

### 4.6 Coleta do DODF no GitHub Actions

O DODF é coletado **fora** do ambiente da rotina, por
`.github/workflows/coleta-dodf.yml`. Motivo em `docs/ISSUES.md` §1: o proxy do
ambiente não alcança `dodf.df.gov.br` e não há entrada de allowlist que resolva
num ambiente já criado. O Actions roda dentro do GitHub, sem esse proxy.

Como funciona:

1. Todo dia às 09:00 UTC (06:00 em Brasília) o workflow baixa a edição, extrai o
   texto e roda a **seleção** do pré-filtro (o mesmo `config/dicionario.md`).
2. Publica só os blocos selecionados — alguns KB — em
   `data/dodf/<data>/blocos.json`, na branch **`dados/dodf`**. É uma branch
   órfã: não tem o resto do repositório e guarda 60 dias de cache.
3. O passo 1 do `SKILL.md` traz esses blocos com
   `git fetch origin dados/dodf && git archive origin/dados/dodf | tar -x`. O
   `prefiltro.py` os encontra em `data/dodf/` e aplica dedup e hash normalmente.

O que precisa estar configurado no repositório:

- **Settings → Actions → General → Workflow permissions: "Read and write
  permissions"** — sem isso o push na branch `dados/dodf` falha. É a única
  configuração manual necessária.
- O cron precisa rodar **antes** do horário da rotina. Se mudar o horário da
  rotina, ajuste o cron junto.

Nada disso depende do 403 de push da rotina (`docs/ISSUES.md` §7): o workflow
usa o `GITHUB_TOKEN` emitido pelo GitHub, que não passa pelo proxy do Claude.

**Relay no VPS (caminho principal desde 12/08/2026).**

*Por que existe:* o firewall do GDF derruba a conexão TLS vinda do IP da VM da
nuvem — o proxy do Claude libera o host, a conexão sai, e o **destino** corta
com reset (diagnóstico completo, com as três hipóteses erradas pelo caminho, em
`docs/ISSUES.md` §1). Nenhuma allowlist resolve isso, porque o bloqueio é do
lado do governo. O mesmo VPS que roda a Evolution API, porém, **é aceito** pelo
GDF — então um relay nele fecha o circuito:

```
rotina (nuvem) ──HTTPS──> Traefik (EasyPanel) ──> nginx dodf-relay ──HTTPS──> dodf.df.gov.br
```

O VPS roda **EasyPanel**, então não se edita nginx por SSH: o relay é um
serviço do painel. Passo a passo (validado em 12/08/2026):

1. No projeto do EasyPanel: **+ Service → App**, nome `dodf-relay`.
2. Em **Source**: imagem Docker `nginx:alpine`.
3. Em **Mounts → Add Mount → File Mount**, Mount Path
   `/etc/nginx/conf.d/default.conf`, com este conteúdo:

   ```nginx
   server {
       listen 80;

       # DNS embutido do Docker, resolvido em runtime. Com hostname fixo no
       # proxy_pass o nginx resolve só no boot — se o DNS falhar nesse
       # instante, o container entra em crash-loop e o Traefik devolve 502.
       resolver 127.0.0.11 valid=300s ipv6=off;

       # --- DODF (PDF do diário do DF) ---
       location /dodf/ {
           set $dodf https://dodf.df.gov.br;
           proxy_pass $dodf$request_uri;         # preserva caminho + query
           proxy_set_header Host dodf.df.gov.br;
           proxy_ssl_server_name on;
           proxy_ssl_name dodf.df.gov.br;
           proxy_read_timeout 300s;
           proxy_buffering off;                  # PDFs grandes: stream direto
       }

       # --- INLABS (XML do DOU; login com cookies de sessão e de WAF) ---
       location /inlabs/ {
           rewrite ^/inlabs/(.*)$ /$1 break;
           set $inlabs https://inlabs.in.gov.br;
           proxy_pass $inlabs;
           proxy_set_header Host inlabs.in.gov.br;
           proxy_ssl_server_name on;
           proxy_ssl_name inlabs.in.gov.br;
           # Os cookies precisam valer no domínio do relay, e os redirects do
           # login não podem jogar o cliente de volta no host real.
           proxy_cookie_domain inlabs.in.gov.br $host;
           proxy_cookie_path / /inlabs/;
           proxy_redirect https://inlabs.in.gov.br/ /inlabs/;
           proxy_read_timeout 300s;
           proxy_buffering off;                  # zips do DOU são grandes
       }

       # --- www.in.gov.br (índice que dá o link exato da matéria) ---
       location /ingov/ {
           rewrite ^/ingov/(.*)$ /$1 break;
           set $ingov https://www.in.gov.br;
           proxy_pass $ingov;
           proxy_set_header Host www.in.gov.br;
           proxy_ssl_server_name on;
           proxy_ssl_name www.in.gov.br;
           proxy_read_timeout 120s;
       }

       location / { return 404; }
   }
   ```

   Cada `location` é um destino fixo — não é proxy aberto.

4. Em **Domains**: adicione um domínio com **Port 80** (o EasyPanel gera um
   subdomínio `*.easypanel.host`; o Traefik cuida do HTTPS sozinho). Anote o
   hostname — ele vai na allowlist e no `DODF_BASE_URL`. **Não recrie o
   serviço à toa**: recriar pode trocar o subdomínio e quebrar os dois.
5. **Deploy**, e teste de qualquer máquina:
   - `curl -sI https://RELAY/` → **404** é o esperado (é o `location /` da
     config — prova que o nginx subiu com ela);
   - `curl -sI https://RELAY/dodf/jornal/visualizar-pdf` → **404 também é
     sucesso**: é o DODF respondendo que o caminho sem parâmetros não existe —
     a chamada atravessou até o GDF e voltou;
   - prova definitiva:
     `DODF_BASE_URL=https://RELAY python scripts/coleta_dodf.py` deve baixar
     os PDFs do dia.
6. No **ambiente de nuvem** (formulário de Update cloud environment), as duas
   metades — e depois de salvar, **abra uma sessão nova** (sessões abertas
   congelam a configuração de rede do momento em que iniciaram):
   - Network access → Custom → Allowed domains: o hostname do relay;
   - env vars, uma por fonte:

     ```
     DODF_BASE_URL=https://RELAY
     INLABS_BASE_URL=https://RELAY/inlabs
     IN_GOV_BASE_URL=https://RELAY/ingov
     ```

   Como o proxy do ambiente passou a recusar domínios `.gov.br` por categoria
   (13/08/2026 — `CONNECT 403` até em host que funcionava antes), **as três
   fontes** passam pelo relay. Sem as variáveis, os scripts falam direto com os
   sites — é o modo local, e continua funcionando.

Falhas conhecidas e o que significam:

| Sintoma | Causa | Ação |
|---|---|---|
| `502` em tudo, inclusive na raiz | nginx em crash-loop (DNS no boot) | conferir que a config é a acima (com `resolver`); logs do serviço no painel |
| `200` com página de boas-vindas do nginx | File Mount não aplicou | conferir o Mount Path e re-deploy |
| `404` na raiz | **normal** — assinatura da config | — |
| `ProxyError: Tunnel connection failed: 403` na nuvem | allowlist sem o host do relay, ou sessão aberta antes de salvar | conferir a entrada, salvar, sessão nova |

O coletor baixa pelo relay e **os links entregues à cliente continuam no site
oficial** (`coleta_dodf.py` reescreve a URL). Sem `DODF_BASE_URL`, o coletor
fala direto com `dodf.df.gov.br` — é o modo local/Actions.

**Diagnóstico quando o DODF sumir do resumo:** com o relay ativo, confira o VPS
(`curl` acima) e o alerta técnico da rotina. No caminho do Actions, abra a aba
Actions do repositório: falha do workflow = coleta quebrada; sucesso com
`blocos.json` vazio = houve diário e nada casou com o dicionário. O texto
integral do dia fica como artifact da execução por 14 dias.

### 4.7 Limites úteis de saber

- Intervalo mínimo entre execuções: **1 hora** (irrelevante para rotina diária).
- A execução pode começar alguns minutos após o horário agendado (é normal).
- Há um limite diário de execuções de rotinas por conta (consumo em
  <https://claude.ai/settings/usage>).
- A VM da rotina tem ~4 vCPUs / 16 GB RAM / 30 GB de disco — muito acima do que
  esta automação precisa.
- Push: a nuvem sempre aceita push em branches `claude/*`. Push direto na
  `master` pode ser recusado com **403 pelo proxy de git do ambiente** mesmo com
  o app do GitHub autorizado com escrita — foi o observado em 10/08/2026. O
  passo 8 do SKILL.md já prevê o fallback (branch `claude/estado-*` + PR) e a
  verificação com `git ls-remote`; se o 403 persistir todo dia, o PR diário
  precisa ser mergeado manualmente ou a restrição removida no painel.
- Docs oficiais: <https://code.claude.com/docs/en/routines.md> e
  <https://code.claude.com/docs/en/cloud-environments.md>.

## 5. Manutenção

- **Ajustar o alcance do pré-filtro**: edite [`config/dicionario.md`](../config/dicionario.md)
  (uma linha `- termo` por palavra-chave; sem acentos é suficiente). Commit + push
  e a próxima execução já usa a lista nova.
- **Fontes**: [`config/fontes.md`](../config/fontes.md) documenta URLs e seções.
- **Deduplicação**: `data/vistos.json` guarda os hashes já processados. Ele
  precisa voltar para o GitHub (commit/push ao fim da run — passo 7 do SKILL.md)
  para valer entre execuções. Se crescer demais, pode ser truncado mantendo os
  últimos ~90 dias.
- **Sem mensagem recebida?** Ordem de diagnóstico: (1) a rotina rodou? (2) env
  vars presentes no ambiente da rotina? (3) instância Evolution conectada
  (QR code pode expirar)? (4) INLABS logando? (5) havia edição do diário no dia?
