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

> Nota: a rede de SANÇÃO é propositalmente mais ampla que o gatilho do lead. Aqui
> entram rescisão, advertência e impedimento porque com frequência acompanham a
> multa no mesmo ato. Quem separa é a qualificação: **sem multa não vira lead**
> (regra 1 da Tarefa 2 em `prompts/rotina_sancoes.md`).

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
- atraso injustificado
- termo de apenacao
- apenacao
- processo administrativo sancionador
- processo administrativo de responsabilizacao
- apuracao de responsabilidade
- notificacao de penalidade
- aplicacao de penalidade
- decisao de aplicacao
- clausula penal
- glosa
- art. 156
- artigo 156
- art. 87
- artigo 87
- lei 13.303
- lei no 13.303
- regulamento de licitacoes e contratos

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
- terracap
- valec
- infra s.a.
- infra s/a
- sodf
- infraestrutura viaria
- malha viaria
- malha rodoviaria
- via urbana
- estrada
- crema
- br-legal
- revitaliza
- proarte
- superintendencia regional
- obras rodoviarias
- restauracao rodoviaria
- engenharia pesada

## Órgãos-âncora (contam como rede RODOVIA)

Órgãos cuja simples menção junto de um termo de sanção já qualifica o trecho:

- departamento nacional de infraestrutura de transportes
- agencia nacional de transportes terrestres
- ministerio dos transportes
- secretaria de obras
- secretaria de estado de obras
- companhia urbanizadora da nova capital
- companhia imobiliaria de brasilia
- departamento de estradas de rodagem
- departamento de engenharia e construcao
