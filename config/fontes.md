# Fontes fixas

O agente só coleta destas fontes. Não navegar livremente pela web.

## 1. DOU — Diário Oficial da União (via INLABS)

- **O que é:** portal da Imprensa Nacional que distribui as edições do DOU em XML/PDF
  para usuários cadastrados (cadastro gratuito).
- **URL base:** `https://inlabs.in.gov.br`
- **Autenticação:** login por e-mail/senha (env vars `INLABS_LOGIN` / `INLABS_SENHA`).
  O login cria uma sessão (cookie) usada nos downloads.
- **Arquivos:** por data, zips XML por seção — padrão de nome
  `AAAA-MM-DD-DO1.zip`, `-DO2.zip`, `-DO3.zip` (+ edições extras `-DO1E.zip` etc.).
- **Seções de interesse:**
  - **Seção 1** — atos normativos e decisões (declarações de inidoneidade, sanções
    aplicadas por ministérios/agências como ANTT e DNIT).
  - **Seção 3** — extratos de contratos, avisos de penalidade, apostilamentos,
    notificações de multa contratual. **É onde sai a maioria dos leads.**
  - Seção 2 (pessoal) normalmente não interessa — baixa opcional.
- **Link público da publicação (para o lead):** montado por `scripts/links_dou.py`,
  nunca pelo LLM. Dois níveis, nesta ordem:
  1. **Link da matéria** — `https://www.in.gov.br/web/dou/-/<urlTitle>`. O
     `urlTitle` não está no XML; vem do JSON que a página `leiturajornal` do dia
     embute (`<script id="params">`), casado com a matéria por página + prefixo
     do texto. Abre só a publicação, sem garimpo.
  2. **Link da página** (reserva) —
     `https://www.in.gov.br/leiturajornal?data=DD-MM-AAAA&secao=doX&pagina=N`.
     Atenção ao formato: data em **DD-MM-AAAA** (o resto do projeto usa
     AAAA-MM-DD) e seção em minúsculas.
- **Página impressa:** atributo `numberPage` do `<article>`. É a fonte de verdade
  — confere com a `pagina` da URL `pdfPage` em 774/774 matérias do DO1+DO3 de
  07/08/2026, e com os metadados que o próprio site exibe ("Edição: N | Seção: X
  | Página: P") em 22/22 links conferidos.

## 2. DODF — Diário Oficial do Distrito Federal

- **O que é:** diário oficial do GDF; publica sanções de contratos distritais
  (Secretaria de Obras, DER-DF, NOVACAP etc.).
- **URL base:** `https://dodf.df.gov.br`
- **Autenticação:** nenhuma (acesso público).
- **Acesso:** o site expõe a edição do dia para download em PDF (e a listagem de
  arquivos por diretório de data). O script `coleta_dodf.py` monta a URL da edição
  do dia.
- **Onde a coleta roda:** no **GitHub Actions**, não na rotina — o ambiente de
  nuvem não alcança este host (`docs/ISSUES.md` §1). O workflow publica os
  blocos já selecionados na branch `dados/dodf`, e a rotina os lê de lá
  (passo 1 do `SKILL.md`). Localmente o script roda normalmente.
- **Seção de interesse:** Seção 3 principalmente (avisos, penalidades, extratos),
  mas o pré-filtro varre o texto completo da edição.
- **Link público da publicação:** o próprio endpoint do PDF com âncora de página —
  `.../visualizar-pdf?pasta=...&arquivo=...#page=N`. O endpoint responde com
  `Content-Disposition: inline`, então o navegador abre o diário já na página
  certa em vez de baixar o arquivo inteiro. A pasta/arquivo de cada PDF ficam em
  `data/raw/dodf/<data>/_edicao.json`, gravado pelo coletor.
- **Página impressa:** lida do rodapé "PÁGINA n" de cada página do PDF, com o
  índice da página como reserva. Conferido na edição 144 de 06/08/2026: rodapé
  presente em 83 das 84 páginas (falta só na capa) e batendo com o índice em
  todas. O rodapé é preferido porque as edições extras têm numeração própria.

## 3. CEIS / CNEP — Portal da Transparência (futuro, NÃO é gatilho)

- Cadastros de empresas sancionadas (CEIS) e punidas por corrupção (CNEP).
- Uso previsto: **enriquecimento mensal** dos leads (histórico da empresa),
  nunca como fonte de lead diário. Ainda não implementado.
