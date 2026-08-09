# Buscador de Sanções — o que precisa ser providenciado

Documento para o cliente. Lista as contas, assinaturas e serviços necessários
para a automação rodar, e os limites que precisam ser conhecidos antes de
começar.

**Recomendação geral:** criar tudo com o **mesmo e-mail corporativo do
escritório** — não com e-mail pessoal de sócio ou funcionário. Se a pessoa sair,
o acesso fica com o escritório.

---

## 1. Contas e serviços

| # | O quê | Custo | Para quê |
|---|---|---|---|
| 1 | **E-mail corporativo** | já existe | Cadastro de todo o resto |
| 2 | **GitHub** | gratuito | Onde fica o código da automação |
| 3 | **Claude Pro** (assinatura) | ~US$ 20/mês | Roda a automação diária (Routines) |
| 4 | **INLABS — Imprensa Nacional** | gratuito | Baixar o Diário Oficial da União |
| 5 | **VPS Hostinger KVM2** | ~R$ 40–70/mês | Servidor do WhatsApp |
| 6 | **Número de WhatsApp dedicado** | custo do chip/plano | Número que envia os alertas |
| 7 | **Portal da Transparência — API** *(opcional)* | gratuito | CNPJ e registro de sanção das empresas |

**Total mensal aproximado: R$ 150 a R$ 200**, considerando a assinatura do Claude
em dólar. Confirmar os valores no momento da contratação.

### Detalhes de cada item

**2. GitHub** — cadastro gratuito. O repositório fica privado.

**3. Claude Pro** — é o plano mínimo que libera as *Routines* (tarefas
agendadas). Planos superiores (Max) só são necessários se o volume crescer — ver
a seção de limites abaixo.

**4. INLABS** — cadastro gratuito no site da Imprensa Nacional, confirmação por
e-mail. Guardar login e senha.

**5. VPS Hostinger KVM2** — servidor onde roda o EasyPanel com a Evolution API
(a ferramenta gratuita que envia as mensagens de WhatsApp). Eu faço toda a
configuração; o escritório só precisa contratar o plano e me dar acesso.

**6. Número de WhatsApp** — recomendo um **número separado, só da automação**,
não o número pessoal nem o do escritório.

**7. Portal da Transparência** — chave de API gratuita, pedida por e-mail. Sem
ela a automação funciona igual; o que se perde é o CNPJ da empresa quando o
diário não traz, e o link do cadastro de sanções.

---

## 2. Limites que precisam ser conhecidos

### 2.1 Limite de uso do Claude — o mais importante

A assinatura do Claude não é ilimitada. O uso é contado em duas janelas:

- **Janela de ~5 horas** — a cada bloco de cinco horas de uso há um teto; ao
  atingi-lo, é preciso esperar a janela reabrir.
- **Limite semanal** — além do teto de 5 horas, existe um teto por semana.

**O risco prático:** se o limite for consumido por uso manual (conversas,
análises, outros projetos na mesma conta), **a rotina daquele dia pode não
rodar** — e o escritório perde os leads do dia, justamente quando o prazo de
defesa está correndo.

**Como reduzir esse risco:**

- Usar uma conta Claude **dedicada à automação**, separada do uso do dia a dia.
- Se a mesma conta for usada para outras coisas, evitar uso pesado no horário da
  rotina (manhã).
- Acompanhar o consumo em `claude.ai/settings/usage`.
- Se faltar limite com frequência, subir para o plano Max.

Os números exatos de cada limite mudam com o tempo e com o plano — consultar a
página de consumo acima para os valores vigentes.

### 2.2 Outros limites e riscos

| Risco | O que acontece | Gravidade |
|---|---|---|
| **Limite de execuções de rotina por dia** | A conta tem um teto diário de execuções agendadas. Para uma rotina diária, folgado. | Baixa |
| **Fonte do governo fora do ar** | Se o DOU ou o DODF estiver indisponível, a automação avisa na mensagem e segue com a outra fonte. | Média |
| **Bloqueio de acesso ao DODF** | Pendência conhecida, em tratamento. Enquanto isso o DOU (federal) continua funcionando. | Média |
| **VPS fora do ar** | Se o servidor do WhatsApp cair, a mensagem não chega. O lead não se perde (fica na planilha), mas o aviso atrasa. | Média |
| **Desconexão do WhatsApp** | A conexão do número pode cair e precisar de novo QR code. É preciso alguém reconectar. | Média |
| **Banimento do WhatsApp** | Risco baixo: são poucas mensagens por dia, para dois destinatários conhecidos. Configuro intervalo entre envios para reduzir ainda mais. | Baixa |
| **Dia sem publicação** | Fim de semana e feriado não têm diário. A mensagem do dia vem como "sem novidades". | Nenhuma |

### 2.3 Sobre a qualidade dos dados

- Quando o diário não traz o valor da multa, o lead vem marcado como **"valor a
  apurar"** — precisa de conferência manual. É proposital: melhor conferir do que
  perder o lead.
- O **prazo de defesa é uma estimativa** calculada a partir da data de
  publicação. Serve para priorizar, **não substitui a conferência do processo**.
- A automação **encontra e organiza** os leads. A decisão de abordar é sempre do
  escritório.

### 2.4 Confidencialidade

O ambiente de nuvem do Claude ainda não tem cofre de senhas dedicado — as
credenciais ficam visíveis para quem usa aquele ambiente. Por isso a
recomendação de contas dedicadas à automação, com o mínimo de permissão
necessária.

---

## 3. Divisão do trabalho

**O escritório providencia:**

1. As contas e assinaturas da seção 1, todas com o e-mail corporativo.
2. O número de WhatsApp dedicado (chip disponível para leitura do QR code).
3. Os dados de acesso, entregues por canal seguro.
4. Um notebook da empresa disponível para a configuração inicial.

**Eu configuro:**

1. Instalação do Claude no notebook do escritório.
2. Conexão com o GitHub e publicação do repositório.
3. Variáveis de ambiente e domínios liberados.
4. Servidor VPS: EasyPanel, Evolution API, conexão do número de WhatsApp.
5. Criação e agendamento da rotina diária.
6. Teste de ponta a ponta antes de entregar.

**Depois de pronto**, a operação do dia a dia é: receber a mensagem no WhatsApp
pela manhã e consultar a planilha de histórico. Nada mais precisa ser feito
manualmente.

---

## 4. Ordem sugerida

1. Criar o e-mail corporativo, se ainda não houver um dedicado.
2. Assinar o Claude Pro. *(sem isso nada roda)*
3. Criar a conta no GitHub.
4. Fazer o cadastro no INLABS.
5. Contratar o VPS na Hostinger.
6. Separar o número de WhatsApp.
7. Pedir a chave do Portal da Transparência. *(opcional, pode ficar para depois)*
8. Agendar a configuração comigo.

Os itens 3 a 7 podem ser feitos em paralelo. O item 2 é o único bloqueante.
