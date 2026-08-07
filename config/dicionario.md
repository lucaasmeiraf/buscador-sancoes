# Dicionário de palavras-chave do pré-filtro

Rede de termos usada por `scripts/prefiltro.py` para **selecionar** trechos
candidatos nos diários. Regras de uso:

- É **seleção**, não extração: um trecho selecionado vai inteiro para o LLM.
- Lista **ampla de propósito** — melhor selecionar demais do que perder lead.
  O LLM descarta o que não for pertinente na etapa de qualificação.
- Editável: adicione/remova termos livremente (uma linha por termo, prefixo `- `).
- A comparação ignora maiúsculas/minúsculas e acentos (o script normaliza), então
  não é preciso duplicar variantes acentuadas.
- Um trecho é candidato se contém **ao menos 1 termo de SANÇÃO** e **ao menos 1
  termo de RODOVIA** (o script permite afrouxar isso por flag — ver `prefiltro.py`).

## Rede SANÇÃO (o que aconteceu)

- multa
- multas
- penalidade
- penalidades
- sancao
- sancoes
- sancionar
- sancionada
- sancionatorio
- inidonea
- inidoneidade
- impedimento de licitar
- impedida de licitar
- suspensao temporaria
- advertencia
- rescisao contratual
- rescisao unilateral
- descumprimento contratual
- inexecucao parcial
- inexecucao total
- inadimplemento
- processo administrativo sancionador
- processo administrativo de responsabilizacao
- apuracao de responsabilidade
- notificacao de penalidade
- aplicacao de penalidade
- decisao de aplicacao
- clausula penal
- glosa

## Rede RODOVIA (a quem/sobre o quê)

- rodovia
- rodovias
- rodoviario
- rodoviaria
- pavimentacao
- pavimento
- recapeamento
- asfalto
- asfaltica
- cbuq
- terraplenagem
- terraplanagem
- duplicacao
- restauracao de rodovia
- conservacao rodoviaria
- manutencao rodoviaria
- sinalizacao viaria
- sinalizacao horizontal
- sinalizacao vertical
- obra de arte especial
- ponte
- viaduto
- passarela
- drenagem
- contorno viario
- anel viario
- br-
- df-
- dnit
- antt
- der-df
- der/df
- novacap
- infraestrutura viaria
- malha viaria
- malha rodoviaria
- via urbana
- estrada

## Órgãos-âncora (contam como rede RODOVIA)

Órgãos cuja simples menção junto de um termo de sanção já qualifica o trecho:

- departamento nacional de infraestrutura de transportes
- agencia nacional de transportes terrestres
- ministerio dos transportes
- secretaria de obras
- companhia urbanizadora da nova capital
