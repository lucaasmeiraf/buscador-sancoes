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
- **Link público da publicação (para o lead):** buscar a matéria em
  `https://www.in.gov.br/leiturajornal?data=DD-MM-AAAA&secao=doX` ou usar a URL
  presente nos metadados do XML (atributo da matéria, quando disponível).

## 2. DODF — Diário Oficial do Distrito Federal

- **O que é:** diário oficial do GDF; publica sanções de contratos distritais
  (Secretaria de Obras, DER-DF, NOVACAP etc.).
- **URL base:** `https://dodf.df.gov.br`
- **Autenticação:** nenhuma (acesso público).
- **Acesso:** o site expõe a edição do dia para download em PDF (e a listagem de
  arquivos por diretório de data). O script `coleta_dodf.py` monta a URL da edição
  do dia; conferir/ajustar o endpoint na primeira execução real.
- **Seção de interesse:** Seção 3 principalmente (avisos, penalidades, extratos),
  mas o pré-filtro varre o texto completo da edição.
- **Link público da publicação:** URL do PDF da edição + página, ou o link de
  visualização da matéria no próprio site.

## 3. CEIS / CNEP — Portal da Transparência (futuro, NÃO é gatilho)

- Cadastros de empresas sancionadas (CEIS) e punidas por corrupção (CNEP).
- Uso previsto: **enriquecimento mensal** dos leads (histórico da empresa),
  nunca como fonte de lead diário. Ainda não implementado.
