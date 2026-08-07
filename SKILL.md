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

## 3. Extração via LLM

- Abra `prompts/rotina_sancoes.md` e siga-o como prompt de extração.
- Processe os trechos de `data/candidatos.json` (em lotes, se forem muitos) e produza
  um JSON por trecho com os campos: empresa, CNPJ, órgão sancionador, tipo de
  penalidade, valor da multa (ou percentual + valor do contrato), objeto do contrato,
  nº contrato/processo, data de publicação, fase processual.
- Não descarte nada nesta etapa — a qualificação vem depois.

## 4. Qualificação

Aplique, nesta ordem:

1. **Objeto** — se claramente NÃO for infraestrutura rodoviária (pavimentação,
   rodovia, obra de arte especial, sinalização viária, conservação rodoviária etc.),
   descarte. Em dúvida, mantenha.
2. **Valor** — multa ≤ R$ 200.000,00 expressa no texto → descarte. Valor **não
   expresso** (ou só percentual sem base) → **mantenha** com marcação `"valor a apurar"`.
3. **Prazo** — estime o prazo de defesa/recurso a partir da data de publicação
   (regra prática: 10 dias úteis para defesa prévia; 15 dias em processos da Lei
   14.133/2021 — indique que é estimativa). Priorize publicações recentes.
4. **Reincidência** — se a mesma empresa aparecer em mais de um trecho (hoje ou no
   histórico de `data/vistos.json`), sinalize "múltiplas sanções".

## 5. Montar o resumo diário

Para cada lead qualificado, monte o pacote:

> empresa · CNPJ · órgão · penalidade · valor · objeto · nº contrato/processo ·
> data de publicação · prazo estimado de defesa · fase processual · link da publicação

Formato da mensagem: português claro, um bloco por lead, leads mais urgentes
primeiro (prazo mais curto). Se não houver leads: mensagem única
**"Sem novidades hoje — nenhuma sanção qualificada nos diários de <data>."**
Inclua ao final avisos de falha de coleta, se houver.

## 6. Enviar por WhatsApp

```bash
python scripts/enviar_whatsapp.py --arquivo data/resumo.txt
```

(ou importe `enviar_whatsapp.enviar_texto()` e passe a mensagem montada).

## 7. Persistir estado

- Acrescente os hashes dos trechos processados hoje a `data/vistos.json`.
- **Commit + push** de `data/vistos.json` para o repositório (é isso que preserva a
  deduplicação entre execuções, já que o Routines clona o repo limpo a cada run).
- Não commite nada de `data/raw/` nem `data/candidatos.json`.

## Regras permanentes

- Nunca escreva segredos em arquivos ou logs.
- Nunca use regex para extrair campos — regex/palavra-chave é só para **selecionar**.
- Não navegue livremente pela web: use apenas as fontes de `config/fontes.md`.
- Custo: não envie o diário inteiro ao LLM; só os trechos pré-filtrados.
