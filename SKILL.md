# SKILL — Rotina diária do Buscador de Sanções

Passo a passo que o agente executa a cada run do Claude Routines. Siga na ordem.
Toda a coleta e o pré-filtro são **determinísticos** (scripts Python). O LLM só entra
na etapa de extração, recebendo trechos já selecionados — nunca o diário inteiro.

## 0. Preparação

- Confirme que as env vars existem: `INLABS_LOGIN`, `INLABS_SENHA`,
  `EVOLUTION_API_URL`, `EVOLUTION_API_KEY`, `EVOLUTION_INSTANCE`, `WHATSAPP_DESTINO`.
  (`WHATSAPP_ADMIN` é opcional — sem ela os alertas técnicos ficam só no log.)
- Se alguma faltar, aborte e registre o erro (não invente valores).
- Cheque o acesso às fontes:

  ```bash
  python scripts/diagnostico_rede.py
  ```

  Não aborte se falhar — o resultado é informativo. Guarde a linha de motivo do
  host que falhou para o **alerta técnico** do passo 6 (ela já diz se a causa é
  a allowlist do ambiente, o WAF do site ou instabilidade). Detalhe técnico
  **nunca** entra na mensagem da cliente.
- Data de referência: hoje (fuso `America/Sao_Paulo`). Em segunda-feira, considere
  também sábado e domingo (o DOU não circula, mas edições extras podem existir).

## 1. Coleta (determinística)

```bash
python scripts/coleta_inlabs.py                      # XML do DOU em data/raw/dou/
python scripts/coleta_dodf.py \
  || (git fetch origin dados/dodf && git archive origin/dados/dodf | tar -x)
```

- **O DODF tem dois caminhos, nesta ordem** (`docs/ISSUES.md` §1):
  1. **Direto** (`coleta_dodf.py`) — funciona se o ambiente alcançar
     `dodf.df.gov.br` (ambiente recriado com a allowlist completa) ou se
     `DODF_BASE_URL` apontar para um relay em host liberado. Em ambiente com o
     host bloqueado, falha em segundos com o motivo diagnosticado — é esperado,
     não é anomalia.
  2. **Branch `dados/dodf`** (o `git fetch` + `git archive` acima) — blocos já
     selecionados que o GitHub Actions (`.github/workflows/coleta-dodf.yml`)
     publica; caem em `data/dodf/<data>/`. O `prefiltro.py` usa o que existir,
     preferindo o texto baixado direto.
- Se **nenhum** dos dois caminhos entregar o DODF de hoje (coleta direta falhou
  E não há `data/dodf/<hoje>/blocos.json`), **siga só com o DOU** e mande os
  dois motivos no alerta técnico do passo 6. Arquivo presente com lista vazia é
  outra coisa: significa que o DODF foi conferido e nada casou — não é falha e
  não vira alerta.
- Se o INLABS falhar, **continue com o DODF**. O motivo diagnosticado que o
  coletor devolve vai **inteiro e sem reinterpretar** para o alerta técnico
  (passo 6); na mensagem da cliente entra no máximo uma linha neutra (passo 5).

## 2. Pré-filtro por seleção (determinístico)

```bash
python scripts/prefiltro.py       # gera data/candidatos.json
```

- O script carrega `config/dicionario.md` e seleciona os trechos/matérias que contêm
  termos das redes de palavras-chave. É **seleção**, não extração: o trecho inteiro
  vai para o LLM, sem recorte de campos por regex.
- Deduplicação: cada trecho recebe hash SHA-256; hashes já presentes em
  `data/vistos.json` são descartados.
- Cada candidato já vem com **`link`, `pagina` e `edicao` prontos e conferidos**,
  vindos dos metadados oficiais (`numberPage`/`urlTitle` do INLABS; rodapé
  "PÁGINA n" do PDF do DODF). Esses campos são **copiados**, nunca recalculados —
  ver o aviso no topo de `prompts/rotina_sancoes.md`.

## 3. Extração via LLM

- Abra `prompts/rotina_sancoes.md` e siga-o como prompt de extração.
- Os candidatos saem do passo 2 em dois formatos: `data/candidatos.json`
  (canônico, para scripts) e `data/candidatos/NNN-<hash>.txt` — **um arquivo
  por trecho**, com os metadados no cabeçalho e o texto após `--- TEXTO ---`.
- **Leia os arquivos individuais, um a um, e nunca o JSON inteiro** — numa
  edição cheia ele passa de 800KB e estoura o limite da ferramenta de leitura
  (foi o que travou a run de 13/08/2026). Também não concatene tudo num
  arquivo único para ler depois: é o mesmo estouro com outro nome. Se um
  candidato isolado for grande demais para uma leitura (matérias longas do
  DOU existem), leia **esse arquivo** em partes com offset/limit — não mude
  de estratégia.
- Para cada arquivo, produza um JSON com os campos: empresa, CNPJ, órgão
  sancionador, tipo de penalidade, se **tem multa**, valor da multa (ou
  percentual + valor do contrato), fundamento legal, objeto do contrato,
  nº contrato/processo, data de publicação, fase processual — mais
  `link`/`pagina`/`edicao` **copiados do cabeçalho do candidato**.
- Não descarte nada nesta etapa — a qualificação vem depois.

## 4. Qualificação

Aplique, nesta ordem:

1. **Multa** — o gatilho do lead é a **multa** (escopo §1.1). Ato sem multa
   (rescisão, advertência, impedimento, inidoneidade isolados) → **descarte**.
2. **Objeto** — se claramente NÃO for infraestrutura rodoviária (pavimentação,
   rodovia, obra de arte especial, sinalização viária, conservação rodoviária etc.),
   descarte. Em dúvida, mantenha. O filtro é pelo objeto, **nunca pelo órgão**.
3. **Valor** — multa ≤ R$ 200.000,00 expressa no texto → descarte. Percentual com
   valor do contrato no mesmo trecho → calcule e aplique o corte. Valor **não
   expresso** (ou percentual sem base) → **mantenha** com marcação `"valor a apurar"`.
4. **Prazo** — estime o prazo de defesa/recurso a partir da data de publicação
   (regra prática: 10 dias úteis para defesa prévia; 15 dias em processos da Lei
   14.133/2021 — indique que é estimativa). Priorize publicações recentes.
5. **Reincidência** — se a mesma empresa aparecer em mais de um trecho (hoje ou na
   planilha `data/leads.csv`), sinalize "múltiplas sanções".
6. **Registro dos descartes** — para cada candidato descartado que era uma
   **sanção real a empresa identificável**, guarde uma linha curta para o
   rodapé do passo 5: empresa + motivo em linguagem de critério — ex.:
   *"multa de R$ 45 mil, abaixo do corte"*, *"rescisão sem multa"*, *"obra de
   saneamento, fora do escopo rodoviário"*. Trechos que nem eram sanção a
   empresa (pautas, editais, avisos, licenças) **não** ganham linha — entram
   só na contagem agregada.

## 4b. Enriquecimento via CEIS/CNEP

Grave os qualificados em `data/leads_hoje.json` e rode:

```bash
python scripts/enriquecer_sancoes.py --entrada data/leads_hoje.json
```

Preenche CNPJ, link do registro de sanção e histórico da empresa nos cadastros.
Sem `PORTAL_TRANSPARENCIA_TOKEN` o script avisa e devolve os leads intactos —
**não aborte por isso**. Use o arquivo enriquecido nos passos seguintes.

## 5. Montar o resumo diário

Para cada lead qualificado, monte o pacote:

> empresa · CNPJ · órgão · penalidade · valor · fundamento legal · objeto ·
> nº contrato/processo · data de publicação · edição e página · prazo estimado de
> defesa · fase processual · link da publicação

Formato da mensagem: português claro, um bloco por lead, leads mais urgentes
primeiro (prazo mais curto). Se não houver leads, abra com o cabeçalho e a
linha de "sem novidades" do modelo abaixo (o rodapé entra mesmo assim — é ele
que mostra que a checagem aconteceu).

**Formatação para WhatsApp (obrigatória).** A mensagem é lida no celular;
parágrafo corrido vira um bloco ilegível. Regras:

- `*negrito*` só para o título e os nomes de seção; `_itálico_` não é usado
  (em bloco longo o `_` quebra e aparece literal).
- **Um item por linha**, com marcador `•`. Nunca junte itens com ponto e
  vírgula num parágrafo.
- **Linha em branco entre seções.** Nunca quebre linha no meio de uma frase
  para "caber em 80 colunas" — no WhatsApp cada `\n` do arquivo é uma quebra
  real. Uma linha só termina onde o item termina.

**Rodapé de transparência (sempre, inclusive em dia sem lead).** Feche a
mensagem com dois blocos montados a partir de `data/estatisticas.json`
(contagens — nunca estime números) e dos registros do passo 4.6 (motivos).
Modelo de dia sem lead (com leads, os blocos dos leads entram entre o
cabeçalho e o rodapé):

> \*Buscador de Sanções\* — 13/08/2026
>
> Sem novidades hoje: nenhuma sanção qualificada nos diários verificados
> (DOU e DODF).
>
> \*Verificação de hoje\*
> • 2.778 publicações do DOU (seções 1 e 3)
> • 76 páginas do DODF (edição 149)
> • 61 trechos mencionavam sanção ou penalidade; nenhum virou lead
>
> \*Casos analisados e descartados\*
> • Empresa A — multa de R$ 45 mil, abaixo do corte de R$ 200 mil
> • Empresa B — obra de saneamento, fora do escopo rodoviário
> • Mais K casos — multa abaixo do corte
> • Os demais Z trechos não traziam sanção com multa a empresa (editais,
>   licitações, avisos)

(No arquivo `data/resumo.txt` cada `•` é uma linha única, sem a quebra de
72 colunas que este modelo tem por ser Markdown.)

Regras do rodapé:

- No máximo **8 empresas nomeadas**, cada uma na sua linha `• Empresa —
  motivo`; passando disso, agrupe os excedentes por motivo em uma linha
  ("• Mais K casos — multa abaixo do corte").
- Se `estatisticas.json` disser `origem: "externa"` no DODF (sem contagem de
  páginas), a linha do DODF vira só "• DODF (edição E)".
- Motivo é sempre **critério do escopo** (multa, valor, objeto) — nada de
  termo técnico.

**A mensagem da cliente não carrega detalhe técnico.** Se uma fonte não foi
coletada, acrescente no máximo uma linha neutra — ex.: *"Hoje o DODF não pôde
ser verificado; a checagem cobre o DOU."* — sem mencionar proxy, allowlist,
WAF, push, git ou qualquer outro termo de infraestrutura.

## 6. Enviar por WhatsApp

```bash
python scripts/enviar_whatsapp.py --arquivo data/resumo.txt
```

(ou importe `enviar_whatsapp.enviar_texto()` e passe a mensagem montada).

**Alerta técnico (separado, só para o operador):** se houve falha de coleta,
host bloqueado no passo 0 ou qualquer anomalia operacional, envie os detalhes
completos (motivo diagnosticado como veio dos scripts) para o operador:

```bash
python scripts/enviar_whatsapp.py --admin --texto "..."
```

O `--admin` usa `WHATSAPP_ADMIN`; se a variável não existir, o script descarta
o alerta com aviso no log — **nunca** envie conteúdo técnico para
`WHATSAPP_DESTINO` como alternativa.

## 7. Planilha-mestre

Acrescente ao histórico o `data/leads_hoje.json` já enriquecido (passo 4b):

```bash
python scripts/planilha.py --entrada data/leads_hoje.json
```

O script deduplica por hash e **não sobrescreve** a coluna `status`, que a
advogada preenche à mão na planilha.

## 8. Persistir estado

- Acrescente os hashes dos trechos processados hoje a `data/vistos.json`.
- **Commit** de `data/vistos.json` **e `data/leads.csv`** (é isso que preserva a
  deduplicação e o histórico entre execuções, já que o Routines clona o repo
  limpo a cada run). Depois, **push com fallback**, nesta ordem:

  1. `git push origin master`.
  2. Se der **403** (o proxy de git da nuvem pode recusar push direto na branch
     principal), faça `git push origin HEAD:claude/estado-AAAA-MM-DD` — branches
     `claude/*` são sempre aceitas — e abra um PR dessa branch para `master`
     (`gh pr create`; se o `gh` não estiver disponível/autenticado, use o
     servidor MCP do GitHub). Tente o merge imediato
     (`gh pr merge --squash --delete-branch`); se o merge for recusado, deixe o
     PR aberto.
  3. **Verifique sempre**: `git ls-remote origin master` deve apontar para um
     commit que contenha as mudanças de hoje. Não confie no exit code do
     fallback — em 10/08/2026 um push "bem-sucedido" via MCP não chegou ao
     remoto e o estado do dia se perdeu (ver `docs/ISSUES.md` §7).
  4. Se após os passos acima o estado **não** estiver na `master`, envie um
     alerta técnico **ao operador**
     (`python scripts/enviar_whatsapp.py --admin --texto "..."`) avisando:
     estado do dia não persistido + link do PR aberto (ou o erro do push).
     Nunca termine a run silenciosamente nesse caso — e nunca mande esse
     aviso para a cliente (`WHATSAPP_DESTINO`).

- O commit do estado é **whitelist, nunca varredura**: sempre
  `git add data/vistos.json data/leads.csv` — **jamais** `git add -A`,
  `git add .` ou `git commit -a`. Se `git status` mostrar qualquer outro
  arquivo modificado (código, docs, prompts), **não o inclua**: descarte a
  alteração e relate no alerta técnico do passo 6. A rotina não tem mandato
  para alterar a si mesma.

## Regras permanentes

- **A rotina nunca altera nem commita código, prompts, docs ou configuração.**
  Os únicos arquivos que ela commita são `data/vistos.json` e `data/leads.csv`
  (passo 8). Encontrou um bug? Relate no alerta técnico ao operador — não
  conserte.
- Nunca escreva segredos em arquivos ou logs.
- Nunca use regex para extrair campos — regex/palavra-chave é só para **selecionar**.
- Não navegue livremente pela web: use apenas as fontes de `config/fontes.md`.
- Custo: não envie o diário inteiro ao LLM; só os trechos pré-filtrados.
