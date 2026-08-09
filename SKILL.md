# SKILL — Rotina diária do Buscador de Sanções

Passo a passo que o agente executa a cada run do Claude Routines. Siga na ordem.
Toda a coleta e o pré-filtro são **determinísticos** (scripts Python). O LLM só entra
na etapa de extração, recebendo trechos já selecionados — nunca o diário inteiro.

## 0. Preparação

- Confirme que as env vars existem: `INLABS_LOGIN`, `INLABS_SENHA`,
  `EVOLUTION_API_URL`, `EVOLUTION_API_KEY`, `EVOLUTION_INSTANCE`, `WHATSAPP_DESTINO`.
- Se alguma faltar, aborte e registre o erro (não invente valores).
- Data de referência: hoje (fuso `America/Sao_Paulo`). Em segunda-feira, considere
  também sábado e domingo (o DOU não circula, mas edições extras podem existir).

## 1. Coleta (determinística)

```bash
python scripts/coleta_inlabs.py   # baixa XML do DOU do dia em data/raw/dou/
python scripts/coleta_dodf.py     # baixa a edição do dia do DODF em data/raw/dodf/
```

- Se uma fonte falhar (site fora do ar, login inválido), **continue com a outra** e
  informe a falha no resumo final do WhatsApp.

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

## 5. Montar o resumo diário

Para cada lead qualificado, monte o pacote:

> empresa · CNPJ · órgão · penalidade · valor · fundamento legal · objeto ·
> nº contrato/processo · data de publicação · edição e página · prazo estimado de
> defesa · fase processual · link da publicação

Formato da mensagem: português claro, um bloco por lead, leads mais urgentes
primeiro (prazo mais curto). Se não houver leads: mensagem única
**"Sem novidades hoje — nenhuma sanção qualificada nos diários de <data>."**
Inclua ao final avisos de falha de coleta, se houver.

## 6. Enviar por WhatsApp

```bash
python scripts/enviar_whatsapp.py --arquivo data/resumo.txt
```

(ou importe `enviar_whatsapp.enviar_texto()` e passe a mensagem montada).

## 7. Planilha-mestre

Grave os leads **qualificados** (a lista de JSONs, não a mensagem) em
`data/leads_hoje.json` e acrescente-os ao histórico:

```bash
python scripts/planilha.py --entrada data/leads_hoje.json
```

O script deduplica por hash e **não sobrescreve** a coluna `status`, que a
advogada preenche à mão na planilha.

## 8. Persistir estado

- Acrescente os hashes dos trechos processados hoje a `data/vistos.json`.
- **Commit + push** de `data/vistos.json` **e `data/leads.csv`** para o repositório
  (é isso que preserva a deduplicação e o histórico entre execuções, já que o
  Routines clona o repo limpo a cada run).
- Não commite nada de `data/raw/`, nem `data/candidatos.json`, nem `data/leads_hoje.json`.

## Regras permanentes

- Nunca escreva segredos em arquivos ou logs.
- Nunca use regex para extrair campos — regex/palavra-chave é só para **selecionar**.
- Não navegue livremente pela web: use apenas as fontes de `config/fontes.md`.
- Custo: não envie o diário inteiro ao LLM; só os trechos pré-filtrados.
