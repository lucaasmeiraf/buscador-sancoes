# Issues abertas

Pendências conhecidas da automação. Atualizado em 12/08/2026.

---

## 1. A allowlist do ambiente de nuvem só honra o que foi cadastrado na criação

**Status:** contornada em 12/08/2026 (coleta do DODF movida para o GitHub
Actions) — **falta a primeira execução do workflow para confirmar**. A causa
raiz continua aberta, e ainda afeta `www.in.gov.br`.

**Diagnóstico (12/08/2026).** O problema nunca foi do DODF. Cruzando as três
execuções, o que separa host que passa de host que falha é a **data de
cadastro**, não o domínio:

| Host | Entrou na allowlist | Na nuvem |
|---|---|---|
| `inlabs.in.gov.br` | criação do ambiente | passa |
| servidor Evolution | criação do ambiente | passa |
| `dodf.df.gov.br` | edição posterior | bloqueado |
| `www.in.gov.br` | edição posterior | bloqueado |

Nos dois bloqueados o DNS resolve e a conexão é recusada antes de chegar ao
site — recusa do proxy, não do servidor. O ambiente roda com uma versão
congelada da configuração de rede e não herda edições posteriores da allowlist.

Duas consequências:

1. **Qualquer solução que termine em "adicionar o host X na allowlist" está
   morta** — inclusive trocar o DODF por outra fonte (Querido Diário, dados
   abertos do GDF, mirror qualquer): fonte nova é host novo, e host novo é
   bloqueio novo. Vale também para `api.portaldatransparencia.gov.br` (§2).
2. **O DOU está degradado em silêncio.** Com `www.in.gov.br` bloqueado,
   `links_dou.py` cai no link de página em vez do link da matéria. A rotina não
   quebra, então isso não aparecia em lugar nenhum — ver §8.

Descartado por este mesmo diagnóstico: a hipótese de 09/08/2026 de que a
allowlist tinha sido preenchida com `dodf.gov.br` (hostname inexistente em DNS).
Era verdade e foi corrigida para `dodf.df.gov.br` — e o bloqueio continuou,
porque a correção *era uma edição posterior*.

**Contorno aplicado (12/08/2026): coletar fora do sandbox.**
`.github/workflows/coleta-dodf.yml` roda `coleta_dodf.py` + a seleção do
pré-filtro **dentro do GitHub**, que não conhece esse proxy, e publica os blocos
já selecionados (poucos KB/dia) na branch `dados/dodf`. A rotina traz esses
blocos com `git fetch` + `git archive` (passo 1 do `SKILL.md`) — o canal de rede
que comprovadamente funciona de lá, já que o clone de toda run passa por ele.

Escolhido em vez das alternativas por não depender nem do painel do Claude nem
de infraestrutura própria:

- **Relay em host já liberado** (nginx no servidor da Evolution API
  encaminhando para o DODF): funciona, mas põe a coleta e o WhatsApp no mesmo
  ponto único de falha. Fica como plano B, e o código já está pronto para ele —
  basta definir `DODF_BASE_URL` (secret do repositório) apontando para o relay.
- **Recriar o ambiente** com a allowlist completa desde a criação: conserta tudo
  de uma vez e sem código, mas aposta num comportamento de plataforma que pode
  voltar a quebrar na próxima edição da allowlist.

**Verificado localmente em 12/08/2026:** coleta da edição 147 de 11/08 (+ extra
082-A), exportação de 19 blocos selecionados, leitura pela rotina a partir da
branch, e a mecânica git de ponta a ponta num remoto de teste (branch órfã,
clone limpo, extração sem sujar o índice).

**O que falta confirmar na primeira execução do workflow:**

1. Se o WAF do GDF aceita o IP do runner do GitHub (Azure). Sintoma de recusa
   seria 403/503 vindo do site — diferente do bloqueio de proxy. Se acontecer,
   o plano B é o relay via `DODF_BASE_URL`; um self-hosted runner também
   resolveria.
2. Se o repositório está com Settings → Actions → General → Workflow
   permissions em **Read and write** — sem isso o push na branch `dados/dodf`
   falha.
3. Se o horário do cron (09:00 UTC = 06:00 em Brasília) cai mesmo antes do
   horário da rotina.

---

## 2. Enriquecimento por CEIS / CNEP

**Status:** implementado em 09/08/2026 — **falta a chave da API para valer em
produção**, e falta conferir os nomes dos campos da resposta.

`scripts/enriquecer_sancoes.py` consulta os endpoints `/ceis` e `/cnep` da API do
Portal da Transparência e preenche `cnpj` (quando o diário não traz),
`link_registro_sancao` (§4.3) e `sancoes_cadastro` (histórico que alimenta o
sinal de "múltiplas sanções", §3.3).

**O que falta:**

1. **A chave.** Gratuita, chega por e-mail:
   <https://portaldatransparencia.gov.br/api-de-dados/cadastrar-email>. Vai em
   `PORTAL_TRANSPARENCIA_TOKEN`, e `api.portaldatransparencia.gov.br` precisa
   entrar na allowlist. Sem a chave o script avisa e devolve os leads intactos —
   a rotina não quebra. **Atenção:** pela §1, acrescentar esse host à allowlist
   de um ambiente já criado não terá efeito — o enriquecimento vai precisar do
   mesmo tratamento do DODF (rodar fora do sandbox) ou de um ambiente novo.
2. **Conferir o formato da resposta.** Os endpoints e o 401 sem chave foram
   verificados, mas o **corpo** da resposta não — sem chave não dá para ver os
   nomes dos campos. A leitura é defensiva (tenta mais de um caminho por campo e
   guarda o registro bruto em `sancoes_cadastro[].bruto`), então o pior caso é
   campo vindo vazio, não exceção. Na primeira execução com chave, olhar o
   `bruto` e ajustar os caminhos em `_resumir()`.

**Decisão embutida:** CNPJ descoberto por razão social só é aceito quando **todos**
os registros do cadastro concordam num único CNPJ. Havendo divergência, o lead
fica sem CNPJ e com `cnpj_origem: "ambíguo"` — colar o CNPJ da empresa errada num
lead de prospecção é pior do que não ter CNPJ.

**Fora de escopo por ora:** e-Sanções/TCDF (§2 do escopo) não tem API pública
equivalente; ficaria como raspagem, e o CEIS já cobre boa parte do DF.

---

## 3. E-mail diário (Modelo B do escopo) não implementado

**Status:** aberta por decisão — canal atual é WhatsApp.

O escopo §4.1 recomenda "A + B combinados": planilha-mestre + e-mail diário. A
planilha existe desde 09/08/2026 (`data/leads.csv`, via `scripts/planilha.py`) e
o push é feito por WhatsApp (Evolution API) em vez de e-mail. Se o e-mail voltar
a ser requisito, é preciso credencial SMTP nova em env vars.

---

## 4. Reincidência limitada ao que já passou pela planilha

**Status:** parcialmente resolvida.

`data/vistos.json` guarda só hashes de trecho — não dá para saber se uma empresa
já apareceu antes. Desde 09/08/2026 a checagem de "múltiplas sanções" usa
`data/leads.csv`, que acumula razão social e CNPJ. A limitação restante: só
enxerga o histórico **desde que a planilha existe**, e sanções fora do recorte
rodoviário (que nunca viraram lead) continuam invisíveis.

---

## 5. Login do INLABS é intermitente (502 do WAF)

**Status:** mitigada em 09/08/2026.

O `POST /logar.php` alterna entre sucesso e `502 Bad Gateway` para requisições
idênticas, em intervalos de minutos. Duas causas foram separadas:

- **Determinística, corrigida:** um POST sem headers de navegador e sem o GET
  prévio à página de login é sempre recusado — faltam os cookies de desafio do
  WAF (`TS*`). `coleta_inlabs.py` agora faz o GET antes e manda `User-Agent`,
  `Accept-Language`, `Origin` e `Referer`.
- **Intermitente, mitigada:** mesmo com tudo certo o 502 aparece. O script tenta
  até 5 vezes com espera crescente (10s, 20s, ... 50s). Se o INLABS ficar fora
  por mais que isso, a rotina perde o DOU do dia e avisa na mensagem.

---

## 6. `python-dotenv` importado mas não declarado

**Status:** resolvida em 09/08/2026.

`scripts/enviar_whatsapp.py` fazia `from dotenv import load_dotenv` sem o pacote
estar em `requirements.txt` nem no setup script do ambiente de nuvem — o envio
quebraria com `ModuleNotFoundError` numa VM limpa. O import passou a ser
opcional: serve ao teste local e é ignorado na nuvem, onde as variáveis já vêm
do ambiente.

---

## 7. Push do estado na `master` recusado com 403 pelo proxy de git

**Status:** mitigada em 10/08/2026 no passo 8 do `SKILL.md` — falta confirmar
numa execução.

Na run de 10/08/2026, o `git push origin master` do passo 8 (persistência de
`data/vistos.json` e `data/leads.csv`) foi recusado com **403** pelo proxy de
git do ambiente de nuvem, apesar de o app do GitHub estar autorizado (o clone
no início da run funciona). O agente improvisou um push via servidor MCP do
GitHub, que **falhou silenciosamente**: `git ls-remote` local confirmou que
nada chegou ao remoto, e o estado do dia se perdeu (risco de reprocessar os
mesmos trechos no dia seguinte; num dia com lead, mensagem duplicada).

**Mitigação aplicada:** o passo 8 do `SKILL.md` agora define o fallback
determinístico (push em `claude/estado-AAAA-MM-DD` — sempre aceito — + PR +
tentativa de merge), exige verificação com `git ls-remote origin master` e, se
o estado não chegar à `master`, manda um segundo WhatsApp avisando, em vez de
terminar em silêncio.

**Aberto:** se o 403 na `master` for política fixa do proxy (e não configuração
do repositório), o merge do PR diário fica manual — avaliar branch protegida +
auto-merge, ou aceitar o clique diário.

**Não confundir com a §1:** este 403 é do proxy de *git* da nuvem, não do
GitHub, e não afeta o workflow do Actions — lá o push é feito pelo
`GITHUB_TOKEN`, emitido pelo próprio GitHub, sem passar por essa camada.

---

## 8. Link do DOU degradado: `www.in.gov.br` bloqueado na nuvem

**Status:** aberta, descoberta em 12/08/2026 ao diagnosticar a §1.

`www.in.gov.br` é uma das entradas acrescentadas à allowlist depois da criação
do ambiente, e por isso está bloqueada (§1). Sem ela, `links_dou.py` não
consegue ler o `urlTitle` do `leiturajornal` e cai no **link de página**
(`link_tipo: "pagina"`) em vez do link direto da matéria. A rotina não quebra e
a cliente recebe os leads — só com um link que exige garimpar a página.

Não aparecia em lugar nenhum porque o fallback é silencioso por design. Para
medir: `data/candidatos.json` traz `link_tipo` em cada candidato, e o
`prefiltro.py` já imprime quantos saíram com link direto.

**Saídas, em ordem de preferência:**

1. Recriar o ambiente com a allowlist completa desde a criação (resolve §1
   inteira, incluindo esta e o Portal da Transparência da §2).
2. Resolver os `urlTitle` no mesmo workflow do Actions que já coleta o DODF,
   publicando um índice do dia na branch `dados/dodf` — mesmo padrão da §1,
   mais código.
3. Aceitar o link de página. É o estado atual.
