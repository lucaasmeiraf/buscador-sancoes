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
| Servidor Evolution API | Enviar WhatsApp | Servidor próprio em nuvem (VPS) com Evolution API v2 instalada |
| Repositório no GitHub | O Routines clona o repo a cada execução | Este repositório publicado no GitHub |
| Python 3.11+ | Rodar os scripts (só para teste local) | <https://python.org> |

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
| `WHATSAPP_DESTINO` | Número da advogada, formato internacional só dígitos (ex.: `5561999998888`) |

### 2.1 INLABS (Imprensa Nacional)

1. Acesse <https://inlabs.in.gov.br> e faça o cadastro (gratuito).
2. Confirme o e-mail e guarde login/senha — são os valores de `INLABS_LOGIN` e
   `INLABS_SENHA`.
3. Teste no navegador: logado, deve ser possível baixar os zips do dia
   (`AAAA-MM-DD-DO1.zip` etc.).

### 2.2 Evolution API (WhatsApp)

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

# 4. teste de envio
python scripts/enviar_whatsapp.py --texto "teste do buscador de sanções"
```

Na primeira execução real, confira os pontos marcados `TODO(1ª execução)` em
`scripts/coleta_inlabs.py` e `scripts/coleta_dodf.py` — são os endpoints exatos
dos sites, que podem ter mudado.

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
   TZ=America/Sao_Paulo
   ```

   As seis primeiras são as mesmas da seção 2 (a lista canônica de nomes está em
   [`.env.example`](../.env.example)). `TZ` não é segredo: a VM da nuvem roda em
   UTC e os scripts usam a data local (`date.today()`), então sem ela uma
   execução agendada para depois das 21h de Brasília buscaria o diário do dia
   seguinte. Às 8h da manhã a data coincide, mas a variável evita a pegadinha
   caso o horário do trigger mude.

3. **Rede**: o ambiente de nuvem passa por um proxy que bloqueia domínios fora da
   lista padrão. Em **Network access → Custom → Allowed domains**, adicione:
   - `inlabs.in.gov.br` (e `www.in.gov.br`, para os links das publicações)
   - `dodf.df.gov.br`
   - o domínio do seu servidor Evolution API

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
python3 -m pip install --break-system-packages -r requirements.txt \
  || python3 -m pip install -r requirements.txt
```

São só duas dependências, declaradas em [`requirements.txt`](../requirements.txt):
`requests` (as três chamadas HTTP: INLABS, DODF, Evolution) e `pypdf` (leitura do
DODF quando a edição vem em PDF). Todo o resto dos scripts é biblioteca padrão do
Python. O `||` é uma salvaguarda: em imagens Debian recentes o pip global recusa
instalar sem `--break-system-packages`, e em imagens mais antigas essa flag não
existe — a linha funciona nos dois casos.

Dois detalhes de comportamento:

- O setup script roda na **criação/atualização do snapshot** do ambiente, não a
  cada execução. As dependências ficam embutidas na imagem — a rotina começa
  rápida e determinística. Se `requirements.txt` mudar, atualize o ambiente para
  o snapshot pegar a versão nova.
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
passo de SKILL.md, na ordem. Ao final, envie o resumo por WhatsApp (script
scripts/enviar_whatsapp.py) e faça commit+push apenas de data/vistos.json.
Se alguma fonte falhar, siga com a outra e relate a falha na mensagem.
```

### 4.6 Limites úteis de saber

- Intervalo mínimo entre execuções: **1 hora** (irrelevante para rotina diária).
- A execução pode começar alguns minutos após o horário agendado (é normal).
- Há um limite diário de execuções de rotinas por conta (consumo em
  <https://claude.ai/settings/usage>).
- A VM da rotina tem ~4 vCPUs / 16 GB RAM / 30 GB de disco — muito acima do que
  esta automação precisa.
- Push: a nuvem sempre aceita push em branches `claude/*`; push direto na branch
  principal funciona se ela não for protegida. Se protegerem a `master`, ajuste o
  passo 7 do SKILL.md para abrir PR em vez de push direto.
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
