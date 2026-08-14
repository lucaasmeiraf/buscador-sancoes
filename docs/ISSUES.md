# Issues abertas

Pendências conhecidas da automação. Atualizado em 12/08/2026.

---

## 0. O proxy do ambiente recusa domínios `.gov.br` por categoria

**Status:** aberta (13/08/2026), contornada pelo relay — a mesma solução da §1,
estendida às três fontes.

**Sintoma:** `CONNECT 403` (recusa do proxy do Claude, antes de sair para a
internet) em `inlabs.in.gov.br` e `www.in.gov.br`, com a allowlist correta e
conferida entrada por entrada. O `inlabs` **funcionava neste mesmo ambiente
até 11/08** e parou sem nenhuma mudança de configuração do nosso lado.

**Por que não é allowlist:** na mesma sessão, o host do relay
(`*.easypanel.host`) — a entrada **mais recente** da lista — passa normalmente.
Edições da allowlist aplicam; o que não passa são os domínios governamentais.
Some-se a isso o `dodf.df.gov.br`, cujo túnel **abria** em 12/08 (a conexão
morria depois, no firewall do GDF — §1) e agora nem abre.

**Contorno:** as três fontes passam pelo relay do VPS
(`docs/CONFIGURACAO.md` §4.6), via `DODF_BASE_URL`, `INLABS_BASE_URL` e
`IN_GOV_BASE_URL`. O VPS alcança as três (medido em 13/08: INLABS 302,
`www.in.gov.br` 301, DODF 202) e o proxy libera o host do relay.

**Validação do relay (madrugada de 13/08/2026):** `/dodf/` com coleta completa
comprovada; `/ingov/` devolvendo o índice real do dia (200, 138KB, com
`urlTitle`); `/inlabs/` entregando os cookies do WAF idênticos ao acesso
direto. O POST de login não pôde ser confirmado porque o INLABS estava **em
manutenção no horário do teste**.

**A confirmação de manhã (13/08) veio negativa:** o POST de login via
`/inlabs/` do relay voltou **200 sem `inlabs_session_cookie`**, enquanto o
acesso **direto** da nuvem funcionou (o `CONNECT 403` do proxy para
`inlabs.in.gov.br` regrediu sozinho, como esperado acima) — a coleta do dia
saiu com `INLABS_BASE_URL` vazia, à mão. Ou seja: credencial correta; o
defeito é específico do login pelo relay.

O que já se sabe do fluxo de login (medido em 13/08, acesso direto):
`GET /logar.php` → 302 `Location: acessar.php`; `POST /logar.php` → 302
`Location: index.php` + `Set-Cookie: inlabs_session_cookie; path=/`. Os
`Location` relativos e o `path=/` são cobertos pela config do relay
(`proxy_cookie_path` reescreve para `/inlabs/`; relativo resolve no cliente) —
a config do §4.6 do `CONFIGURACAO.md` não tem furo óbvio. Hipótese mais forte:
o WAF do Serpro (F5, cookies `TS*`) trata o POST vindo do IP do VPS/da pilha
TLS do nginx diferente do GET, devolvendo a página de login (200) sem
autenticar. **Como confirmar:** de qualquer máquina, rodar o fluxo contra
`https://RELAY/inlabs` com `allow_redirects=False` e comparar o POST — se
vier 200 (e não 302) sem `Set-Cookie` de sessão, o bloqueio é no destino, não
na config do nginx.

**Mitigação no coletor (13/08/2026):** `coleta_inlabs.py` agora tenta a
`INLABS_BASE_URL` configurada e, se o login falhar lá (200 sem cookie ou rota
inalcançável), **cai sozinho para o site oficial** — cobre tanto o defeito do
relay quanto uma eventual volta do `CONNECT 403` do proxy, sem intervenção
manual. `INLABS_BASE_URL` pode ficar definida no ambiente.

**Vale reportar ao suporte da Anthropic:** se for política nova, é bom saber;
se for regressão, tende a voltar sozinha. De qualquer forma o relay já não
depende disso.

---

## 1. O firewall do GDF derruba conexões vindas da VM da nuvem

**Status:** causa raiz identificada em 12/08/2026 (a terceira e definitiva).
Relay **no ar e validado de fora** (12/08 à noite: edição 148 + extra baixadas
de uma máquina local passando pelo relay) — falta só a coleta **pela nuvem**.
A primeira tentativa falhou com `ProxyError: Tunnel connection failed: 403`,
que é assinatura de allowlist: o host do relay não estava valendo na sessão
(entrada ausente ou sessão aberta antes de salvar). Conferir a entrada, salvar,
abrir sessão nova e repetir — tabela de sintomas em `CONFIGURACAO.md` §4.6.

**Causa raiz (12/08/2026, curl -v de dentro do ambiente recriado):**

```
CONNECT tunnel established, response 200   <- o proxy do Claude LIBEROU o host
TLS handshake, Client hello                <- a conexão saiu para a internet
(~11s de silêncio)
Recv failure: Connection reset by peer     <- quem derrubou foi o DESTINO
```

Contraprova no mesmo ambiente: um domínio fora da allowlist (`www.uol.com.br`)
falha **diferente** — `CONNECT tunnel failed, response 403`, recusado pelo
proxy antes de sair. Ou seja: a allowlist estava certa e funcionando; é o
**firewall do GDF** que corta o TLS vindo do IP/faixa da VM do Claude (bloqueio
anti-datacenter). E do VPS da Evolution API (também datacenter, outra faixa) o
DODF responde em 0,4s — o GDF não bloqueia datacenter em geral, bloqueia a
faixa da VM.

**Por que erramos duas vezes antes:** `diagnostico_rede.py` classificava
qualquer `ConnectionError` como bloqueio de proxy — mas o reset do firewall do
destino gera a mesma exceção. As duas hipóteses anteriores (nome errado na
allowlist em 09/08; "allowlist congelada na criação" em 10-12/08) nasceram
dessa classificação errada. O script agora separa as assinaturas (`ProxyError`
= proxy; reset após túnel aberto = firewall do destino), para este erro não se
repetir.

Consequências que continuam valendo:

1. **Nenhuma mudança de allowlist resolve** — o bloqueio é do lado do GDF.
2. **O DOU está degradado em silêncio**: `www.in.gov.br` falha com a mesma
   digital (DNS ok, conexão recusada) — provavelmente o WAF do Serpro fazendo
   o mesmo. `links_dou.py` cai no link de página em vez do link da matéria —
   ver §8.

**Solução escolhida (12/08/2026): relay no servidor da Evolution API.**
O VPS alcança o DODF e o ambiente da nuvem alcança o VPS (host na allowlist,
WhatsApp passa por ele todo dia) — então um `location /dodf/` no nginx do VPS
encaminhando para `https://dodf.df.gov.br` fecha o circuito. O coletor já está
pronto: basta `DODF_BASE_URL` apontando para o domínio do VPS (env var do
ambiente de nuvem), e os links entregues à cliente continuam no site oficial
(o coletor reescreve). Configuração do nginx em `docs/CONFIGURACAO.md` §4.6.

O ponto único de falha (VPS caiu = sem coleta e sem WhatsApp) é aceitável:
sem o VPS a mensagem não sairia de qualquer jeito.

**Alternativa pronta e adormecida: GitHub Actions.**
`.github/workflows/coleta-dodf.yml` roda a coleta + seleção dentro do GitHub e
publica os blocos na branch `dados/dodf`, que a rotina já sabe ler (fallback do
passo 1 do `SKILL.md`). Está bloqueado por outra razão: a conta GitHub está com
trava de cobrança (*"account is locked due to a billing issue"*) — não é custo
do workflow (~90 min/mês, dentro dos 2.000 gratuitos), é pendência da conta em
<https://github.com/settings/billing>. Quando destravar, vale um teste: se o
GDF aceitar o IP do runner (Azure), vira redundância do relay.

**Verificado localmente em 12/08/2026:** coleta das edições 147 e 148 (+
extras), exportação e leitura dos blocos pela via da branch (51 candidatos:
44 DOU + 7 DODF), e a mecânica git de ponta a ponta num remoto de teste.

**O passo 1 do `SKILL.md` é um funil com dois caminhos:** a rotina tenta
`coleta_dodf.py` direto (com `DODF_BASE_URL` definido, isso já sai pelo relay)
e, se falhar, cai para a branch `dados/dodf` do Actions. Alerta técnico só se
**os dois** falharem.

**Para fechar esta issue:**

1. ~~Configurar o relay no VPS~~ — feito em 12/08/2026 (serviço `dodf-relay`
   no EasyPanel; passo a passo em `CONFIGURACAO.md` §4.6) e validado de fora:
   coleta completa da edição do dia atravessando o relay.
2. ~~Allowlist do ambiente com o host do relay + `DODF_BASE_URL`~~ — feito;
   confirmado em 12/08/2026 à noite: **a nuvem baixou o PDF do DODF pelo
   relay**. A rede está fechada de ponta a ponta.
3. Atualizar o **setup script** do ambiente para incluir `cryptography`
   (§4.4 do guia): a imagem da VM traz uma cryptography de sistema quebrada
   que derruba o `import pypdf` com `PanicException` na extração de texto —
   foi a última falha vista. Na sessão, o paliativo é
   `python3 -m pip install --break-system-packages --upgrade cryptography`.
4. Rodar a rotina completa e conferir a mensagem com leads das duas fontes.

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

## 9. Extração travou ao ler `candidatos.json` inteiro

**Status:** resolvida em 13/08/2026 — falta confirmar numa run completa.

Na primeira execução completa pela nuvem (13/08/2026), o agente tentou ler
`data/candidatos.json` de uma vez — 803KB num dia cheio — e a ferramenta de
leitura recusou (limite de 256KB por arquivo). O contorno improvisado
(concatenar tudo num `dump.txt` do scratchpad e ler de novo) estourou o mesmo
limite. A run parou **antes** da extração: nada foi enviado à cliente e
`vistos.json` seguiu vazio, então o dia seguinte reprocessa sem duplicar.

Não é limite de contexto do modelo — é o teto da ferramenta de leitura de
arquivos, e a instrução "em lotes, se forem muitos" do passo 3 era vaga demais
para impedir o engolimento de uma vez.

**Correção (estrutural, não instrucional):** `prefiltro.py` agora grava também
`data/candidatos/NNN-<hash>.txt` — um arquivo de texto por candidato, com
metadados no cabeçalho, linhas quebradas em ≤1000 caracteres (a ferramenta
trunca linhas muito longas) e tamanho típico de poucos KB. O passo 3 do
`SKILL.md` manda ler esses arquivos um a um e proíbe explicitamente o JSON
inteiro e os despejos concatenados. O `candidatos.json` continua existindo
como artefato canônico para scripts.

---

## 8. Link do DOU degradado: `www.in.gov.br` bloqueado na nuvem

**Status:** aberta, descoberta em 12/08/2026 ao diagnosticar a §1.

`www.in.gov.br` falha na nuvem com a mesma digital do DODF (§1): DNS resolve e
a conexão cai — muito provavelmente o WAF do Serpro derrubando o IP da VM, não
o proxy (a allowlist do ambiente recriado está comprovadamente funcionando).
Sem esse host, `links_dou.py` não consegue ler o `urlTitle` do `leiturajornal`
e cai no **link de página** (`link_tipo: "pagina"`) em vez do link direto da
matéria. A rotina não quebra e a cliente recebe os leads — só com um link que
exige garimpar a página.

Não aparecia em lugar nenhum porque o fallback é silencioso por design. Para
medir: `data/candidatos.json` traz `link_tipo` em cada candidato, e o
`prefiltro.py` já imprime quantos saíram com link direto.

**Antes de escolher a saída, confirmar a causa** (mesmo método da §1):

- do VPS: `curl -sS -o /dev/null -w "%{http_code} em %{time_total}s\n" https://www.in.gov.br/` —
  se responder, o VPS serve de relay também para este host;
- da nuvem: `curl -v https://www.in.gov.br/ 2>&1 | tail -8` — reset após
  `CONNECT ... 200` confirma firewall do destino.

**Resolvida em 13/08/2026 pela mesma via da §0:** `links_dou.py` ganhou
`IN_GOV_BASE_URL`, que aponta o **download do índice** para o relay
(`/ingov/`), enquanto `BASE_LEITURA`/`BASE_MATERIA` — os endereços que vão nos
links da cliente — seguem no site oficial. Falta confirmar numa run com a
variável definida: o número de candidatos com `link_tipo: "materia"` deve
voltar aos ~80% medidos localmente (41 de 51 em 12/08).
