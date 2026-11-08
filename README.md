# Projeto3

## FECAP - Fundação de Comércio Álvares Penteado

<p align="center">
  <a href="https://www.fecap.br/">
    <img src="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRhZPrRa89Kma0ZZogxm0pi-tCn_TLKeHGVxywp-LXAFGR3B1DPouAJYHgKZGV0XTEf4AE&usqp=CAU" alt="FECAP - Fundação de Comércio Álvares Penteado" border="0">
  </a>
</p>
<h1 align="center">ASA Turbo · Agentes Inteligentes para o Sucesso do Estudante</h1>

<p align="center">
  Uma pergunta, uma resposta. E nenhum aluno esquecido.
</p>

<p align="center">
  <b>🚀 Acesse a aplicação: <a href="https://asa-turbo.onrender.com">https://asa-turbo.onrender.com</a></b><br>
  <sub>Modo demonstração: entre como Estudante, Atendente ou Administrador sem precisar de conta.</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-Entrega%202-green" alt="Status">
  <img src="https://img.shields.io/badge/agentes-Estudante%20%2B%20Monitoramento-green" alt="Agentes">
  <img src="https://img.shields.io/badge/turma-5º%20CCOMP%20·%202º%20sem%202026-blue" alt="Turma">
  <img src="https://img.shields.io/badge/licença-CC%20BY--SA%204.0-lightgrey" alt="Licença"></p>

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

**O problema.** A informação existe, mas está espalhada em regulamentos, manual do aluno, Moodle e documentos de várias áreas, e o atendimento acontece em canais que não se conversam (presencial, e-mail, WhatsApp e portal). O estudante enfrenta fila, troca de canal e às vezes recebe **respostas diferentes para a mesma pergunta**. Ao mesmo tempo, o risco de evasão costuma ser percebido tarde demais: o contato preventivo é manual e o sistema preditivo atual cobre poucos alunos.

**A solução.** O **ASA Turbo** é uma plataforma de IA com dois agentes e três perfis de acesso:

| Perfil | O que faz |
|---|---|
| 🎓 **Estudante** | Chat que responde em segundos a partir **somente de documentos oficiais**, com fonte e data de atualização em cada resposta. Sem base suficiente, não inventa: encaminha para uma pessoa da equipe do ASA. |
| 🧑‍💼 **Atendente** | **Fila de risco de evasão** (Verde, Amarelo, Vermelho) ordenada por prioridade. Mostra o score, a tendência dos últimos meses, os fatores que mais pesaram e uma recomendação sugerida. O atendente confirma, ajusta ou rejeita a faixa, com justificativa registrada. |
| 🛠️ **Administrador** | **Painel** de uso com números agregados (perguntas, abstenção, avaliações, tempo de resposta) e gestão da **base de conhecimento** (cadastro, versão e desativação de documentos). |

> **O score é apoio, não veredito.** Nenhuma ação com impacto acadêmico, financeiro ou disciplinar é tomada pela IA. O estudante nunca vê a tela de risco.

---

## 🔍 Descoberta com o parceiro

Levantamento feito junto à equipe do ASA. Um ponto importante de contexto: **o ASA não é uma área de atendimento**, mas acaba precisando responder o estudante e acompanhar sua trajetória.

| Dor levantada | Como o ASA Turbo responde |
|---|---|
| Canais fragmentados, filas e espera | Chat único, disponível a qualquer hora, com encaminhamento para humano quando necessário. |
| Informação espalhada e documentos longos | Base de conhecimento centralizada; resposta curta com o trecho relevante. |
| **Inconsistência de informação** | A mesma pergunta recupera o mesmo documento oficial, com fonte e data visíveis. |
| Busca difícil também para quem atende | A equipe mantém a base pelo perfil Administrador. |
| Risco de evasão percebido tarde | Fila de risco com fatores explicáveis e tendência, para priorizar o contato. |

---

## 🤖 Como funciona

### Agente para o Estudante (chat RAG)

```text
Pergunta do estudante
        ↓
Embedding da pergunta (bge-m3, 1024 dimensões)
        ↓
Busca vetorial na base de conhecimento oficial (pgvector)
        ↓
Similaridade acima do limiar?
   ├── sim → resposta com o trecho recuperado + fonte + data
   └── não → abstenção e encaminhamento para a equipe do ASA
```

- Resposta **extrativa**: o texto vem do documento oficial, não é gerado por um modelo de linguagem.
- Perguntas de continuação ("e o prazo?") são reescritas com o contexto da conversa.
- Embeddings com fallback: Cloudflare Workers AI → Hugging Face → TF-IDF local → abstenção.

### Agente de Monitoramento (risco de evasão)

```text
Dados acadêmicos e financeiros
        ↓
Modelo XGBoost monotônico calibrado
        ↓
Score + faixa (Amarelo ≥ 30%, Vermelho ≥ 60%) + fatores que mais pesaram
        ↓
Recomendação sugerida por regra
        ↓
Avaliação humana obrigatória (confirmar / ajustar / rejeitar + justificativa)
```

- Restrições de monotonia garantem direções coerentes (por exemplo, mais parcelas em aberto nunca reduz o risco).
- Sexo, estado civil e contatos com o ASA **não entram no modelo**: procurar ajuda nunca piora o score.

### Princípios inegociáveis

1. **Conhecimento oficial.** O agente nunca inventa procedimento, prazo ou regra.
2. **Fonte e data sempre.** Toda resposta mostra de onde veio e quando foi atualizada.
3. **Abstenção é resposta válida.** Sem evidência suficiente, encaminha para atendimento humano.
4. **Decisão assistida.** O score é apoio, não veredito; toda decisão é humana e auditada.
5. **Privacidade e LGPD.** Minimização de dados; controle de acesso por perfil; nenhum dado pessoal, credencial ou token versionado.
6. **Acessibilidade.** Linguagem clara, contraste adequado, navegação por teclado e compatibilidade com leitores de tela.

---

## 📊 Resultados (Entrega 2)

Números extraídos do [relatório de resultados](src/Entrega%202/docs/entrega_ia/relatorio_resultados.md) e do [Model Card v2](src/Entrega%202/docs/entrega_ia/model_card_v2.md).

**Chat do estudante (RAG, 60 perguntas de avaliação)**

| Métrica | bge-m3 (produção) |
|---|---|
| Recall@1 / Recall@3 | 93,8% / 95,8% |
| Acerto do agente | 90% |
| Abstenção correta (fora do escopo) | 100% |
| Groundedness | 100% (resposta extrativa) |

**Modelo de risco (XGBoost monotônico, conjunto de teste)**

| Métrica | Valor |
|---|---|
| AUC-ROC | 0,913 |
| Recall | 76% (de cada 100 alunos que evadiram, 76 teriam sido sinalizados) |
| Precisão | 64% |
| F1 | 0,691 |

> **Limitações:** a avaliação do RAG usa 20 documentos fictícios e precisa ser refeita com a base real do ASA. O rótulo de evasão não teve o período de referência confirmado formalmente com o parceiro.

---

## 🔗 Integração com o TOTVS

O TOTVS é o sistema acadêmico da FECAP. A integração fica isolada atrás de um contrato próprio, então a troca pela API real é possível, caso a FECAP/ASA autorize o acesso, sem mudanças nos agentes.

---

## 🏗 Arquitetura

```text
Navegador (React + Vite, PWA)
        ↓  /api
API FastAPI (container único no Render, também serve o frontend)
   ├── Autenticação e perfis (Supabase Auth / modo demonstração)
   ├── Chat RAG  ──→ Embeddings (Cloudflare → Hugging Face → TF-IDF)
   │             ──→ Supabase Postgres + pgvector
   ├── Risco     ──→ Modelo XGBoost (artefato versionado em ml/artifacts)
   ├── Casos, validação humana e auditoria
   ├── Painel e base de conhecimento
   └── /health e /metrics (Prometheus + Grafana)
```

Em modo demonstração (`DEMO_MODE=true`), a API sobe sem banco externo, com os dados carregados em memória.

---

## 🧰 Tecnologias

| Camada | Ferramentas |
|---|---|
| Frontend | React 18, Vite, CSS Modules, PWA |
| Backend e API | Python 3.12, FastAPI, Pydantic, contrato OpenAPI (`docs/api-contract.yaml`) |
| Agente RAG | Embeddings bge-m3 (Cloudflare Workers AI / Hugging Face), fallback TF-IDF |
| Modelo de risco | XGBoost, scikit-learn, pandas, SHAP |
| Banco de dados | Supabase (Postgres 16 + pgvector, RLS por perfil) |
| Nuvem e infraestrutura | Docker (multi-stage, usuário não-root), Render; alternativas Fly.io e Caddy documentadas |
| Observabilidade | Logs JSON, Prometheus, Grafana |
| Qualidade | pytest, ruff, Playwright (e2e), testes de carga e acessibilidade |
| Álgebra Linear | Python: vetores, similaridade de cosseno, PCA e redução de dimensionalidade |
| Versionamento | Git e GitHub |

---

## 📂 Estrutura de pastas

```text
📁 documentos
 ├── 📁 Entrega1             # entregáveis acadêmicos da Entrega 1
 └── 📁 Entrega 2            # entregáveis acadêmicos da Entrega 2
📁 src
 ├── 📁 Entrega 1            # protótipo da Entrega 1 (HTML + função serverless no Vercel)
 └── 📁 Entrega 2            # ASA Turbo (versão atual)
      ├── 📁 backend         # API FastAPI, RAG, risco, autenticação e testes
      ├── 📁 web             # frontend React + Vite
      ├── 📁 ml              # treino e avaliação (risco e RAG), notebooks e artefatos
      ├── 📁 infra           # SQL, Docker, deploy, monitoramento e testes de carga
      ├── 📁 e2e             # testes ponta a ponta (Playwright)
      ├── 📁 seeds           # dados para demonstração
      ├── 📁 docs            # contrato da API, decisões, relatório e evidências
      └── 📄 Dockerfile      # container único (API + web)
📄 render.yaml               # blueprint de deploy no Render
📄 README.md
```

> Dados pessoais, credenciais e arquivos restritos não são versionados.

---

## ▶️ Como executar

### 🌐 Acessar a aplicação publicada

**👉 [https://asa-turbo.onrender.com](https://asa-turbo.onrender.com)**

Na tela de entrada, use **Acessar como demonstração** e escolha um perfil:

| Perfil | O que explorar |
|---|---|
| Estudante | Chat com a base oficial e perguntas frequentes |
| Atendente | Fila de risco, detalhe do caso e modelo |
| Administrador | Painel, fila de risco, base de conhecimento e modelo |

> O Render, no plano gratuito, desliga o serviço quando fica ocioso. O primeiro acesso pode levar até um minuto para carregar.

### 🐳 Rodar localmente com Docker

```bash
cd "src/Entrega 2"
docker build -t asa-turbo .
docker run --rm -p 8080:8080 -e PORT=8080 asa-turbo   # DEMO_MODE=true por padrão
# abra http://localhost:8080
```

Para rodar backend e frontend separados, ou usar o Supabase real, veja [backend/README.md](src/Entrega%202/backend/README.md) e [infra/README.md](src/Entrega%202/infra/README.md).

### 🕰️ Versão da Entrega 1

O protótipo da Entrega 1 continua publicado em [projeto-ia-rho.vercel.app](https://projeto-ia-rho.vercel.app/) e o código está em `src/Entrega 1/`.

---

⚠️ Atraso nas entregas 1 e 2 custa 25% da nota total por dia.

### Escopo por entrega

**Entrega 1.** Definição do problema, usuários e jornadas; requisitos e critérios de aceitação; riscos éticos e plano de proteção de dados; arquitetura preliminar; catálogo de fontes e base de conhecimento inicial; contrato da integração com o TOTVS e mock funcionando; recuperação de documentos funcionando, com avaliação de relevância e respostas com fontes; notebook de Álgebra Linear com pelo menos duas operações; ambiente Linux/nuvem documentado; primeira versão do Model Card; prova de conceito e protótipo.

**Entrega 2.** MVP integrado e publicado na nuvem; fluxo completo de pergunta, resposta com evidências, próxima ação, encaminhamento humano e histórico; dashboard gerencial; comparação de configurações, métricas de qualidade do ranking, cobertura, groundedness e taxa de resposta correta; casos de abstenção, limitações e análise de viés; versionamento da base de conhecimento e endpoint de inferência; Model Card final e relatório de extensão.

O projeto integra as Unidades Curriculares de **Inteligência Artificial e Aprendizado de Máquina**, **Álgebra Linear, Vetores e Geometria Analítica**, **Sistemas Operacionais e Computação em Nuvem**, **Psicologia, Liderança e Soft Skills** e **Projeto Interdisciplinar**.

---

## 📋 Licença

Este projeto está licenciado sob a [Creative Commons BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

## 🎓 Referências

- [FECAP · Área do Sucesso Alvarista (ASA)](https://www.fecap.br/asa/)
- Enunciado do Projeto Interdisciplinar · ASA · 5º CCOMP · 2º semestre de 2026 (versão FINAL)
