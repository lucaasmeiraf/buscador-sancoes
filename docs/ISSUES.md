# Issues abertas

Pendências conhecidas da automação. Atualizado em 09/08/2026.

---

## 1. DODF bloqueado no ambiente de nuvem (Routines)

**Status:** causa identificada em 09/08/2026 — falta corrigir a allowlist e
confirmar numa execução. Impacto alto enquanto aberta (perde-se metade das
fontes: DER/DF, SODF, Terracap, Novacap).

**Sintoma:** `scripts/coleta_dodf.py` falha nas execuções do Claude Routines por
bloqueio de acesso a `dodf.df.gov.br`. Localmente (rede residencial) o mesmo
script funciona — reconferido em 09/08/2026, listando a edição 145 de 07/08/2026
e a edição extra 081-A.

**Causa identificada (09/08/2026):** a allowlist do cloud environment foi
preenchida com `dodf.gov.br` — um hostname que **não existe em DNS**
(`NameResolutionError`; conferido também nas variantes `dodf.gov` e
`www.dodf.gov.br`, igualmente inexistentes). O host real tem um `df.` no meio:
**`dodf.df.gov.br`** (131.72.221.239, faixa do próprio GDF; título da página:
"Sistema de busca do novo Diário Oficial do Distrito Federal"). O formato da
entrada estava certo (só hostname); o nome é que estava incompleto — com isso o
proxy libera um domínio que não existe e segue bloqueando o que o script chama.

O trace de 09/08/2026 também estabeleceu que o fluxo toca **um único host**
(`dodf.df.gov.br`) — sem redirect, sem CDN, sem segundo domínio. A allowlist
precisa de exatamente uma entrada.

**Correção (no painel, não no código):** em Network access → Custom → Allowed
domains do cloud environment, trocar `dodf.gov.br` por `dodf.df.gov.br`.
Nenhum script ou doc do repositório precisa mudar — todos já apontam para
`dodf.df.gov.br`.

**Hipóteses residuais, se falhar mesmo após a correção:**

1. **WAF do GDF recusando o IP de datacenter da VM** — sintoma é 403/503 vindo
   do site, não do proxy. Mitigação já aplicada: `coleta_dodf.py` manda
   `User-Agent` de navegador completo, `Accept-Language` e `Referer` (o mesmo
   que destravou o INLABS, issue 5).
2. **Instabilidade** — coberta pelo retry (3 tentativas, espera crescente).

**Como confirmar sem esperar a rotina:** rodar
`python scripts/diagnostico_rede.py` dentro do ambiente de nuvem — ele
classifica cada host (DNS, proxy, WAF, timeout) e diz a ação correspondente.

**Enquanto não fecha:** a rotina segue com o DOU e avisa a falha no fim da
mensagem (comportamento já previsto no passo 1 do `SKILL.md`).

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
   a rotina não quebra.
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
