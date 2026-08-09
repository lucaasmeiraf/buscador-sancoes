# Issues abertas

Pendências conhecidas da automação. Atualizado em 09/08/2026.

---

## 1. DODF bloqueado no ambiente de nuvem (Routines)

**Status:** aberta — impacto alto (perde-se metade das fontes: DER/DF, SODF,
Terracap, Novacap).

**Sintoma:** `scripts/coleta_dodf.py` falha nas execuções do Claude Routines por
bloqueio de acesso a `dodf.df.gov.br`. Localmente (rede residencial) o mesmo
script funciona — conferido em 09/08/2026, baixando a edição 144 de 06/08/2026
(íntegra, 84 páginas) e a edição extra 080.

**Hipóteses, em ordem de custo para testar:**

1. `dodf.df.gov.br` não está na *allowlist* do ambiente de nuvem
   (Network access → Custom → Allowed domains). Ver `docs/CONFIGURACAO.md` §4.3.
   O domínio precisa estar listado exatamente assim, sem `https://` e sem barra.
2. O site recusa o IP de datacenter da VM (WAF do GDF). Nesse caso a allowlist
   não resolve: o sintoma é 403/503 vindo do próprio site, não do proxy.
   Diagnóstico: numa run, comparar o corpo da resposta com o de uma execução
   local — página de bloqueio do site é diferente de erro de proxy.
3. O `POST /dodf/jornal/diario` exige o header `X-Requested-With` (já enviado) e
   um `User-Agent` de navegador — hoje o script manda
   `Mozilla/5.0 (buscador-sancoes)`. Se a hipótese 2 se confirmar, testar um UA
   de navegador completo (foi exatamente isso que destravou o INLABS, issue 5).

**Enquanto não resolve:** a rotina segue com o DOU e avisa a falha no fim da
mensagem do WhatsApp (comportamento já previsto no passo 1 do `SKILL.md`).

---

## 2. Enriquecimento por CEIS / CNEP / e-Sanções não implementado

**Status:** aberta por decisão — adiada em 09/08/2026 para priorizar a precisão
dos links.

O escopo (§2) trata o cruzamento com os cadastros de sanção como parte da busca,
não como extra: "uma multa contratual pode sair no DOU como 'Termo de Apenação'
sem CNPJ e sem valor; o mesmo caso aparece no CEIS/CNEP já com CNPJ e
enquadramento". Dois campos do pacote de entrega (§3.2 e §4.3) dependem disso:

- `cnpj` — hoje fica "não informado" sempre que o diário não traz o número;
- **link do registro de sanção** — hoje não existe no lead.

**Para implementar:** API do Portal da Transparência
(`api.portaldatransparencia.gov.br`, endpoints CEIS e CNEP), que exige cadastro e
chave própria (`PORTAL_TRANSPARENCIA_TOKEN`). Somar o domínio à allowlist do
ambiente de nuvem.

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
