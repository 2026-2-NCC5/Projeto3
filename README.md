# Projeto3

## FECAP - Fundação de Comércio Álvares Penteado

<p align="center">
  <a href="https://www.fecap.br/">
    <img src="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRhZPrRa89Kma0ZZogxm0pi-tCn_TLKeHGVxywp-LXAFGR3B1DPouAJYHgKZGV0XTEf4AE&usqp=CAU" alt="FECAP - Fundação de Comércio Álvares Penteado" border="0">
  </a>
</p>
<h1 align="center">ASA · Agentes Inteligentes para o Sucesso do Estudante</h1>

<p align="center">
  Agente para o Estudante: respostas curtas, confiáveis e com fonte, sobre serviços e procedimentos da FECAP.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-em%20desenvolvimento-yellow" alt="Status">
  <img src="https://img.shields.io/badge/agente-Agente%20para%20o%20Estudante-green" alt="Agente">
  <img src="https://img.shields.io/badge/integração-TOTVS-orange" alt="Integração">
  <img src="https://img.shields.io/badge/turma-5º%20CCOMP%20·%202º%20sem%202026-blue" alt="Turma">
  <img src="https://img.shields.io/badge/licença-CC%20BY--SA%204.0-lightgrey" alt="Licença">
</p>

---

## 👥 Grupo: EriTech +

| Integrante | GitHub |
|---|---|
| Bruno Eduardo da Silva Pinho | [@Smug303](https://github.com/Smug303) |
| Eric Victor Bittu Silva | [@eric-bittu](https://github.com/eric-bittu) |
| Vivian Kaori Umaki | [@vivikari](https://github.com/vivikari) |
| Yanko Lee | [@Yanko-dev](https://github.com/Yanko-dev) |

### 📚 Professor orientador

- [Rafael Diogo Rossetti](https://www.linkedin.com/in/rafael-diogo-rossetti/)

### 📔 Orientadores complementares

- Marcelo de Moura Amorim
- Marcos Minoru Nakatsugawa
- [Rodnil da Silva Moreira Lisboa](https://www.linkedin.com/in/professorrodnil/)
- Rodrigo da Rosa

---

## 📖 Sobre o projeto

A **Área do Sucesso Alvarista (ASA)** acolhe e acompanha os estudantes ao longo da jornada na FECAP, com uma equipe multidisciplinar e serviços que vão de biblioteca e financiamento a empregabilidade e carreira.

**O problema.** A informação existe, mas não resolve. Regulamentos, manual do aluno, Moodle e documentos de várias áreas ficam espalhados na rede, e o estudante não quer ler dez páginas para descobrir um prazo. O atendimento acontece em canais que não se conversam (presencial, e-mail, WhatsApp e portal do aluno), então quem não recebe resposta imediata vai trocando de canal e entrando em nova fila. Pior: a mesma pergunta pode receber **respostas diferentes de dois atendentes**, e essa inconsistência mina a confiança do estudante na informação oficial.

**A solução.** Um **Agente para o Estudante** que consome as fontes oficiais do ASA e da FECAP, cruza com os dados acadêmicos do estudante vindos do **TOTVS** e devolve uma resposta curta, com passo a passo, canal correto, fonte citada e data de atualização. Uma pergunta, uma resposta, sem fila e sem depender de qual atendente atendeu.

**Referência de sucesso.** Uma resposta é boa quando é **curta** (o estudante quer duas linhas, não o documento), **fundamentada** (sai da base oficial, com fonte e data), **personalizada** (considera a situação real de quem perguntou), **consistente** (a mesma pergunta gera a mesma resposta) e **honesta** (quando não há base suficiente, o agente se abstém e transfere para atendimento humano em vez de inventar).

---

## 🔍 Descoberta com o parceiro

Levantamento feito junto à equipe do ASA. Um ponto importante de contexto: **o ASA não é uma área de atendimento**, mas acaba precisando responder o estudante e acompanhar sua trajetória.

### Dores que o nosso agente ataca

| Dor levantada | Situação hoje |
|---|---|
| Canais fragmentados | Presencial, e-mail, WhatsApp e portal do aluno não se conversam; sem plataforma integrada. |
| Filas e espera | Sem resposta imediata, o estudante troca de canal e recomeça a espera. |
| Informação espalhada | Regulamentos, manual do aluno, Moodle e documentos de várias áreas salvos na rede. |
| Documentos longos demais | O estudante quer a resposta em duas linhas, não um PDF de dez páginas. |
| **Inconsistência de informação** | Dois atendentes respondem a mesma pergunta de formas diferentes. |
| Busca difícil também para quem atende | A própria equipe quer facilitar a localização da informação correta. |
| Resposta genérica não resolve | Sem saber a situação do estudante, a orientação não chega ao caso concreto dele. |

O ASA já está trabalhando na **centralização dessas fontes**, o que conversa diretamente com a base de conhecimento do agente.

### Dores registradas, mas fora do escopo principal

O enunciado permite **um agente como escopo principal**, então o que segue fica documentado como contexto e possível extensão:

- Acompanhamento preventivo e predição de evasão. Hoje o contato é manual e o sistema preditivo em uso tem baixa acurácia, cobre cerca de 150 estudantes e sinaliza o risco tarde demais.
- Painel para atendentes e coordenadores com acesso rápido à vida do estudante.
- Integração entre o sistema acadêmico e o CRM que concentra WhatsApp, e-mail e senhas de atendimento.

---

## 🤖 Como o agente funciona

```text
Pergunta do estudante
        ↓
Perfil de acesso + contexto acadêmico (TOTVS)
        ↓
Busca na base de conhecimento oficial (RAG)
        ↓
Resposta curta + passo a passo + canal/link + fonte + data
        ↓
Sem base suficiente?  →  abstenção e transferência para atendimento humano
```

| Entrada | O que é |
|---|---|
| 📚 Base de conhecimento | Conteúdo institucional autorizado: regulamentos, manual do aluno, procedimentos, FAQs e materiais das áreas do ASA. |
| 🔗 Dados do TOTVS | Situação acadêmica e administrativa autorizada do estudante, usada para interpretar a dúvida e personalizar a orientação. |
| 👤 Perfil de acesso | Define o que aquele usuário pode ver e receber. |
| 🧭 Contexto da solicitação | Canal, histórico da conversa e o que o estudante já tentou. |

### Princípios inegociáveis

1. **Conhecimento oficial.** O agente responde a partir de conteúdo institucional autorizado. Nunca inventa procedimento, prazo ou regra.
2. **Fonte e data sempre.** Toda resposta mostra de onde veio e quando aquele conteúdo foi atualizado.
3. **Abstenção é resposta válida.** Sem evidência suficiente, o agente não arrisca: encaminha para atendimento humano.
4. **Decisão assistida.** Nada com impacto acadêmico, financeiro ou disciplinar é decidido pelo agente.
5. **Privacidade e LGPD.** Dados anonimizados, agregados ou fictícios; minimização, controle de acesso e nenhum dado pessoal, credencial ou token versionado no repositório.
6. **Acessibilidade.** Linguagem clara, contraste adequado, navegação por teclado e compatibilidade com leitores de tela.

O projeto integra as Unidades Curriculares de **Inteligência Artificial e Aprendizado de Máquina**, **Álgebra Linear, Vetores e Geometria Analítica**, **Sistemas Operacionais e Computação em Nuvem**, **Psicologia, Liderança e Soft Skills** e **Projeto Interdisciplinar**.

---

## 🔗 Integração com o TOTVS

O TOTVS é o sistema acadêmico da FECAP e a fonte da informação que hoje o estudante só consegue depois de abrir requisição no portal ou entrar em uma fila. Trazer esse contexto para dentro do agente é o que separa uma resposta genérica de uma resposta útil: em vez de explicar como funciona a rematrícula em tese, o agente explica o que **aquele** estudante precisa fazer, na situação em que ele está.

**O que a integração habilita**

- Interpretar a dúvida a partir da situação real do estudante, e não só do texto da pergunta.
- Responder sobre prazos, requisitos e pendências já aplicados ao caso concreto.
- Indicar o próximo passo certo e o canal correto, evitando o vaivém entre canais.

**Como a integração é desenhada**

| Decisão | Abordagem |
|---|---|
| Acoplamento | Camada de integração isolada atrás de uma interface própria. O agente consome um contrato interno, não o TOTVS diretamente. |
| Desenvolvimento e demo | **Mock com dados fictícios** implementando o mesmo contrato, para o projeto rodar e ser demonstrado sem depender de acesso ao ambiente real. |
| Escopo dos dados | Somente os campos autorizados e necessários para responder à dúvida, aplicando minimização. |
| Segurança | Credenciais e tokens em variáveis de ambiente e gestão de segredos da nuvem. Nada versionado no repositório. |
| Rastreabilidade | Registro de origem, versão e data dos dados consultados, respeitando o nível de acesso. |

> **Status:** acesso ao ambiente TOTVS ainda **pendente de autorização** da FECAP/ASA. Enquanto isso, o desenvolvimento segue pelo mock com dados fictícios, o que mantém o MVP entregável mesmo que a liberação não saia a tempo.

---

## 🏗 Arquitetura

```text
Aplicação  ->  API  ->  Base de conhecimento versionada
                     ->  Índice vetorial (embeddings)
                     ->  Camada de integração  ->  TOTVS (dados acadêmicos autorizados)
                                               ->  Mock com dados fictícios
                     ->  Agente RAG  ->  Resposta com fontes
                                     ->  Encaminhamento humano
                                     ->  Feedback, histórico e auditoria
                     tudo executado em infraestrutura de nuvem
```

> **Decisão em aberto:** o enunciado define aplicação mobile. O grupo avalia uma alternativa web, ainda pendente de aprovação dos professores e do ASA. Atualizar esta seção assim que a decisão for validada.

---

## 🧰 Tecnologias

| Camada | Ferramentas |
|---|---|
| Aplicação | *a definir conforme a decisão de escopo* |
| Backend e API | Python com FastAPI ou Flask |
| Agente e RAG | Embeddings, busca vetorial, LangChain ou LlamaIndex, modelo de linguagem autorizado |
| Base de conhecimento | Ingestão e versionamento de documentos oficiais |
| Integração | TOTVS via API autorizada, com mock de dados fictícios para desenvolvimento e demo |
| Álgebra Linear | Python: vetores, matrizes, similaridade e redução de dimensionalidade |
| Banco de dados | Relacional + banco vetorial *(a definir)* |
| Nuvem | Docker + provedor a definir (AWS, Azure ou GCP) |
| Observabilidade | Logs estruturados e métricas de aplicação e de qualidade das respostas |
| Versionamento | Git, GitHub e GitHub Projects |
| Documentação | OpenAPI/Swagger, Model Card, relatório técnico |

---

## 📂 Estrutura de pastas

```text
📁 Documentos
 ├── 📁 Entrega_1        # documentação da Entrega 1
 └── 📁 Entrega_2        # documentação da Entrega 2
📁 src
 ├── 📁 backend          # API, banco, autenticação, integração TOTVS e auditoria
 ├── 📁 mobile           # aplicação (ver decisão em aberto acima)
 └── 📁 notebooks        # ingestão, embeddings, Álgebra Linear e avaliação
📄 .gitignore
📄 README.md
```

> Dados pessoais, credenciais e arquivos restritos não são versionados. O repositório usa apenas **amostras fictícias** para execução e demonstração.

---

## ▶️ Como executar

> Preencher conforme o ambiente for sendo montado.

```bash
git clone https://github.com/<organizacao>/<repositorio>.git
cd <repositorio>

# backend
cd src/backend
# copiar o arquivo de exemplo de variáveis de ambiente e preencher
# a integração roda em modo mock por padrão, sem necessidade de acesso ao TOTVS
# instruções de instalação e execução

# notebooks
cd ../notebooks
# instruções de instalação e execução
```

---

⚠️ Atraso nas entregas 1 e 2 custa 25% da nota total por dia.

### Escopo por entrega

**Entrega 1.** Definição do problema, usuários e jornadas; requisitos e critérios de aceitação; riscos éticos e plano de proteção de dados; arquitetura preliminar; catálogo de fontes e base de conhecimento inicial; contrato da integração com o TOTVS e mock funcionando; recuperação de documentos funcionando, com avaliação de relevância e respostas com fontes; notebook de Álgebra Linear com pelo menos duas operações; ambiente Linux/nuvem documentado; primeira versão do Model Card; prova de conceito e protótipo.

**Entrega 2.** MVP integrado e publicado na nuvem; fluxo completo de pergunta, resposta com evidências, próxima ação, encaminhamento humano e histórico; dashboard gerencial; comparação de configurações, métricas de qualidade do ranking, cobertura, groundedness e taxa de resposta correta; casos de abstenção, limitações e análise de viés; versionamento da base de conhecimento e endpoint de inferência; Model Card final e relatório de extensão.

---

## 📋 Licença

Este projeto está licenciado sob a [Creative Commons BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

## 🎓 Referências

- [FECAP · Área do Sucesso Alvarista (ASA)](https://www.fecap.br/asa/)
- Enunciado do Projeto Interdisciplinar · ASA · 5º CCOMP · 2º semestre de 2026 (versão FINAL)
