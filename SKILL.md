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
git fetch origin dados/dodf && git archive origin/dados/dodf | tar -x
```

- **O DODF não é baixado aqui.** Este ambiente não alcança `dodf.df.gov.br`
  (`docs/ISSUES.md` §1); quem coleta é o GitHub Actions
  (`.github/workflows/coleta-dodf.yml`), que publica os blocos já selecionados
  na branch `dados/dodf`. O `git archive` acima os traz para `data/dodf/<data>/`.
  Não rode `scripts/coleta_dodf.py` — ele vai falhar.
- Se o `fetch` falhar, ou se não houver `data/dodf/<hoje>/blocos.json`, **siga
  só com o DOU** e mande o fato no alerta técnico do passo 6 (o Actions não
  rodou, falhou, ou rodou depois desta run). Arquivo presente com lista vazia é
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
- Processe os trechos de `data/candidatos.json` (em lotes, se forem muitos) e produza
  um JSON por trecho com os campos: empresa, CNPJ, órgão sancionador, tipo de
  penalidade, se **tem multa**, valor da multa (ou percentual + valor do contrato),
  fundamento legal, objeto do contrato, nº contrato/processo, data de publicação,
  fase processual — mais `link`/`pagina`/`edicao` **copiados do candidato**.
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
primeiro (prazo mais curto). Se não houver leads: mensagem única
**"Sem novidades hoje — nenhuma sanção qualificada nos diários de <data>."**

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

- Não commite nada de `data/raw/`, nem `data/candidatos.json`, nem `data/leads_hoje.json`.

## Regras permanentes

- Nunca escreva segredos em arquivos ou logs.
- Nunca use regex para extrair campos — regex/palavra-chave é só para **selecionar**.
- Não navegue livremente pela web: use apenas as fontes de `config/fontes.md`.
- Custo: não envie o diário inteiro ao LLM; só os trechos pré-filtrados.
