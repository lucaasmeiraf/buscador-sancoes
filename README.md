# Buscador de Sanções

Automação diária que localiza, nos diários oficiais (DOU e DODF), **empresas de
infraestrutura rodoviária multadas acima de R$ 200 mil** em contratos federais e do
Distrito Federal, e envia os leads qualificados por **WhatsApp** (Evolution API) para a
advogada.

## Como funciona (visão geral)

1. **Coleta determinística** — scripts Python baixam as edições do dia:
   - **DOU** via INLABS (Imprensa Nacional), arquivos XML (requer login — env vars).
   - **DODF** via site oficial do GDF.
2. **Pré-filtro por seleção** — os textos são varridos com uma lista **ampla e
   editável** de palavras-chave (`config/dicionario.md`) e/ou por seção do diário.
   O pré-filtro apenas **seleciona trechos candidatos**; ele não extrai campo nenhum.
3. **Localização da publicação** — ainda no pré-filtro, cada trecho recebe
   **edição, página impressa e link já prontos**, vindos dos metadados oficiais:
   `numberPage`/`urlTitle` do INLABS (link direto da matéria, quando resolvível)
   e o rodapé "PÁGINA n" do PDF do DODF. O LLM copia esses campos e **nunca monta
   URL** — é o que garante que o link leve à página certa.
4. **Extração via LLM** — o agente (Claude) recebe **somente os trechos selecionados**
   e devolve JSON estruturado com os campos do lead (`prompts/rotina_sancoes.md`).
   Nenhum campo é extraído por regex.
5. **Qualificação** — aplica as regras de corte: **é multa** (sem multa não é lead);
   objeto = infraestrutura rodoviária, qualquer que seja o órgão; valor > R$ 200 mil
   (ou "valor a apurar"); prioriza publicações recentes com prazo de defesa aberto;
   sinaliza empresa reincidente; deduplica por hash.
6. **Enriquecimento** — os leads qualificados passam pelo CEIS/CNEP
   (`scripts/enriquecer_sancoes.py`) para ganhar CNPJ, link do registro de sanção
   e histórico de sanções da empresa. Opcional: sem a chave da API a rotina segue.
7. **Entrega** — resumo diário em português enviado por WhatsApp via Evolution API
   (`scripts/enviar_whatsapp.py`), e os leads acumulados na planilha-mestre
   `data/leads.csv` (`scripts/planilha.py`), com coluna de status para
   acompanhamento. Sem novidade → mensagem "sem novidades hoje".

## Execução no Claude Routines

Este repositório é clonado do GitHub a cada execução agendada (diária, de manhã) pelo
Claude Routines. O agente segue o passo a passo de **`SKILL.md`**. Os segredos
(credenciais INLABS, Evolution API, número de destino) **nunca ficam no código** — são
lidos das environment variables do ambiente de nuvem (nomes em `.env.example`).

Como criar a rotina, configurar o ambiente e agendar: **[docs/CONFIGURACAO.md](docs/CONFIGURACAO.md)**.

> **Atenção (estado entre execuções):** como o Routines clona o repositório limpo a
> cada run, tanto o estado de deduplicação (`data/vistos.json`) quanto a
> planilha-mestre (`data/leads.csv`) só persistem se o agente **commitar e fizer
> push** dos dois ao final da execução (passo previsto no SKILL.md). Sem push, a
> deduplicação vale apenas dentro do mesmo dia e o histórico se perde.

## Estrutura

| Arquivo | Função |
|---|---|
| `README.md` | Este arquivo — o que a automação faz e como o Routines a executa. |
| `SKILL.md` | Passo a passo que o agente segue a cada execução. |
| `CLAUDE.md` | Instrução curta carregada automaticamente pelo agente (aponta para o SKILL.md). |
| `docs/CONFIGURACAO.md` | Guia de configuração: credenciais, teste local e agendamento no Claude. |
| `docs/ISSUES.md` | Pendências conhecidas (DODF na nuvem, CEIS/CNEP, e-mail). |
| `config/fontes.md` | Fontes fixas (DOU/INLABS, DODF) e como acessá-las. |
| `config/dicionario.md` | Rede de palavras-chave do pré-filtro (ampla, editável). |
| `scripts/coleta_inlabs.py` | Baixa as edições XML do DOU via INLABS. |
| `scripts/coleta_dodf.py` | Baixa a edição do dia do DODF (roda no GitHub Actions, não na rotina). |
| `.github/workflows/coleta-dodf.yml` | Coleta diária do DODF fora do ambiente da rotina, publicada na branch `dados/dodf`. |
| `scripts/diagnostico_rede.py` | Testa o acesso às fontes e classifica a falha (allowlist / WAF / instabilidade). |
| `scripts/links_dou.py` | Resolve o link exato da matéria no DOU (página conferida). |
| `scripts/prefiltro.py` | Seleciona trechos candidatos por palavras-chave + dedup por hash. |
| `scripts/enriquecer_sancoes.py` | Completa o lead com CNPJ e registro de sanção via CEIS/CNEP. |
| `scripts/enviar_whatsapp.py` | Envia mensagem via Evolution API (POST). |
| `scripts/planilha.py` | Acumula os leads em `data/leads.csv` sem duplicar nem apagar status. |
| `prompts/rotina_sancoes.md` | Prompt principal de extração/qualificação da rotina. |
| `.env.example` | Nomes das env vars necessárias (sem valores). |

## Escopo

Somente o **Buscador de Sanções**. A automação do ISS é um projeto futuro e **não**
faz parte deste repositório por enquanto. CEIS/CNEP (Portal da Transparência) são
enriquecimento futuro de periodicidade mensal — **não** são gatilho de lead.
