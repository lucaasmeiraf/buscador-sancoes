# Buscador de Sanções — instrução para o agente

Este repositório é uma automação diária executada pelo Claude Routines.

**A cada execução, siga o passo a passo de [`SKILL.md`](SKILL.md)** (coleta →
pré-filtro → extração → qualificação → resumo → WhatsApp → persistir estado).
O prompt de extração está em [`prompts/rotina_sancoes.md`](prompts/rotina_sancoes.md).

Regras permanentes:

- Segredos só via environment variables (nomes em `.env.example`); nunca em
  arquivos, commits ou logs.
- Coleta apenas das fontes de `config/fontes.md` — não navegar livremente.
- Palavras-chave selecionam trechos; a extração de campos é sempre do LLM
  (nunca regex).
- Não construir nem tocar em nada relacionado ao ISS (projeto futuro, fora de escopo).
