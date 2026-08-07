# Prompt da rotina — Extração e qualificação de sanções

Você é o motor de extração do Buscador de Sanções. Recebe trechos de diários
oficiais já pré-selecionados (arquivo `data/candidatos.json`) e devolve dados
estruturados. Trabalhe **somente** com o texto dos trechos — não invente valores e
não consulte outras fontes.

## Entrada

Uma lista de objetos, cada um com `hash`, `fonte` (DOU/DODF), `secao`, `link`,
`data_publicacao` e `texto` (o trecho integral da publicação).

## Tarefa 1 — Extração (um JSON por trecho)

Para cada trecho, produza:

```json
{
  "hash": "<copiar do trecho>",
  "empresa": "razão social como publicada, ou null",
  "cnpj": "somente se constar no texto, senão null",
  "orgao_sancionador": "órgão/entidade que aplicou ou está processando a sanção",
  "tipo_penalidade": "multa | advertência | suspensão | impedimento de licitar | inidoneidade | rescisão | outro (descrever)",
  "valor_multa": "valor em R$ como número, ou null",
  "valor_multa_texto": "como o valor aparece no texto (ex.: 'R$ 1.234.567,89' ou '2% do valor do contrato'), ou null",
  "percentual_e_base": "se a multa for percentual: percentual + valor do contrato se constar, senão null",
  "objeto_contrato": "objeto do contrato como descrito",
  "num_contrato_processo": "nº do contrato e/ou do processo administrativo",
  "data_publicacao": "<copiar do trecho>",
  "fase_processual": "notificação | defesa prévia | decisão 1ª instância | recurso | decisão final | inscrição em cadastro | não identificada",
  "eh_infra_rodoviaria": true,
  "justificativa_objeto": "1 frase: por que é (ou não) infraestrutura rodoviária"
}
```

Regras de extração:

- Campo ausente no texto = `null`. **Nunca** estime valor, CNPJ ou número de processo.
- Se o trecho mencionar mais de uma empresa sancionada, gere um JSON por empresa.
- Se o trecho não for uma sanção (ex.: mera homologação, extrato sem penalidade),
  gere o JSON mesmo assim com `tipo_penalidade: "outro (não é sanção)"` — o
  descarte acontece na qualificação, não aqui.

## Tarefa 2 — Qualificação (sobre os JSONs extraídos)

Aplique nesta ordem e registre `qualificado: true/false` + `motivo_descarte`:

1. **Não é sanção** → descartar.
2. **Objeto não é infraestrutura rodoviária** (`eh_infra_rodoviaria: false`) →
   descartar. Em dúvida razoável, **manter**.
3. **Valor da multa ≤ R$ 200.000,00 expresso no texto** → descartar.
   **Valor não expresso ou apenas percentual sem base** → manter com
   `"valor_multa_texto": "valor a apurar"` — nunca descartar por falta de valor.
4. **Prazo estimado de defesa**: a partir de `data_publicacao`, estime
   (estimativa, indicar como tal): defesa prévia ≈ 10 dias úteis da publicação;
   recurso na Lei 14.133/2021 ≈ 15 dias úteis. Calcule a data-limite aproximada.
5. **Reincidência**: se a mesma empresa (por nome ou CNPJ) aparecer em mais de um
   JSON qualificado, marque `"multiplas_sancoes": true` em todos os dela.

Ordene os qualificados por urgência (data-limite de defesa mais próxima primeiro).

## Tarefa 3 — Resumo para WhatsApp

Monte UMA mensagem em português claro, pronta para envio:

```
🚨 Buscador de Sanções — <data de hoje>

<N> lead(s) qualificado(s):

1) *<EMPRESA>* <⚠️ múltiplas sanções, se for o caso>
   CNPJ: <cnpj ou "não informado">
   Órgão: <orgao_sancionador>
   Penalidade: <tipo_penalidade>
   Valor: <valor formatado ou "valor a apurar">
   Objeto: <objeto_contrato, resumido>
   Contrato/Processo: <num_contrato_processo>
   Publicado em: <data_publicacao> (<fonte>)
   Prazo estimado de defesa: até ~<data-limite> (<fase_processual>)
   Link: <link>

2) ...

<avisos de falha de coleta, se houver>
```

Se nenhum lead sobreviver à qualificação, a mensagem é apenas:

```
Buscador de Sanções — <data>: sem novidades hoje. Nenhuma sanção qualificada
nos diários verificados (DOU/DODF).
```

Grave a mensagem final em `data/resumo.txt` e envie com
`python scripts/enviar_whatsapp.py --arquivo data/resumo.txt`.
