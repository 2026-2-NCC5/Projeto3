# Entregas do PI
### **DECLARAÇÃO DE USO DE INTELIGÊNCIA ARTIFICIAL**

## Entrega 1
<br><br>

### Módulo do sistema 1 · Protótipo

| **Aluno(s) Responsável(veis)** | Eric Victor Bittu Silva, Yanko Lee, Vivian Kaori Umaki, Bruno Eduardo da Silva Pinho |
| :--- | :--- |
| **Ferramenta utilizada** | Claude Code (Anthropic) |
| **Versão/modelo** | Claude Opus 5.5 |
| **Disciplina / Trabalho** | Inteligência Artificial · Projeto Interdisciplinar, Entrega 1 |
| **Finalidade de uso** | Apoio na montagem do protótipo do agente (RAG sobre seeds fictícios), na estrutura inicial do banco no Supabase e na correção de erros do deploy no Vercel. |
| ***Prompts* principais utilizados** | "Como organizo um projeto Python simples com uma rota /api/perguntar no Vercel?"<br>"Esse erro FUNCTION_INVOCATION_FAILED aparece no deploy, o que pode ser?"<br>"Me ajuda a montar o schema.sql com as tabelas de documentos e chunks."<br>"Gera alguns dados fictícios de exemplo para o seed." |
| **Trechos ou entregas afetadas** | `Entrega 1/api/perguntar.py`, `Entrega 1/schema.sql`, `Entrega 1/seed.sql`, `Entrega 1/seed_v2.sql`, `Entrega 1/README.md` |


### Módulo do sistema 2 · Frontend

| **Aluno(s) Responsável(veis)** | Yanko Lee, Vivian Kaori Umaki |
| :--- | :--- |
| **Ferramenta utilizada** | Claude Code (Anthropic) |
| **Versão/modelo** | Claude Opus 5.5 |
| **Disciplina / Trabalho** | Inteligência Artificial · Projeto Interdisciplinar, Entrega 1 |
| **Finalidade de uso** | Apoio no layout da página de chat, ajustes de CSS e integração do front com a rota da API. |
| ***Prompts* principais utilizados** | "Como faço um layout de chat simples, com as mensagens em balões?"<br>"O fetch para /api/perguntar não mostra a resposta na tela, o que está errado?"<br>"Como deixo essa página responsiva no celular?" |
| **Trechos ou entregas afetadas** | `Entrega 1/index.html` (estrutura, estilos e chamada à API) |

### Módulo do sistema 3 · Backend

| **Aluno(s) Responsável(veis)** | Eric Victor Bittu Silva, Bruno Eduardo da Silva Pinho |
| :--- | :--- |
| **Ferramenta utilizada** | Claude Code (Anthropic) |
| **Versão/modelo** | Claude Opus 5.5 |
| **Disciplina / Trabalho** | Inteligência Artificial · Projeto Interdisciplinar, Entrega 1 |
| **Finalidade de uso** | Apoio na geração de embeddings, na busca por similaridade e no fallback TF-IDF quando a API da Hugging Face falha. |
| ***Prompts* principais utilizados** | "Qual modelo da Hugging Face eu uso para gerar embeddings de 384 dimensões?"<br>"Explica como funciona o TF-IDF para usar de fallback."<br>"Como salvo os vetores no Supabase com pgvector?"<br>"A Hugging Face está retornando 403, por quê?" |
| **Trechos ou entregas afetadas** | `Entrega 1/gerar_embeddings.py`, `Entrega 1/connect_supabase.py`, `Entrega 1/idf_table.json`, `Entrega 1/main.py` |

## Entrega 2
<br><br>

### Módulo do sistema 1 · Deploy

| **Aluno(s) Responsável(veis)** | Eric Victor Bittu Silva |
| :--- | :--- |
| **Ferramenta utilizada** | Claude Code (Anthropic) |
| **Versão/modelo** | Claude Opus 5.5 |
| **Disciplina / Trabalho** | Sistemas Operacionais · Projeto Interdisciplinar, Entrega 2 |
| **Finalidade de uso** | Apoio na containerização (Docker e docker compose), no deploy em VM Linux (systemd, firewall ufw, usuário de serviço sem root, permissões do `.env`), no HTTPS com Caddy, no monitoramento (Prometheus, cAdvisor, Grafana), no backup e restauração e no teste de carga. |
| ***Prompts* principais utilizados** | "Como faço um Dockerfile para o backend rodar com usuário não-root?"<br>"Me ajuda a escrever um docker-compose com backend, web e healthcheck."<br>"Como crio um serviço systemd para subir o compose quando a VM liga?"<br>"Quais portas eu libero no ufw para um servidor web?"<br>"Como coloco o Prometheus e o Grafana para monitorar os containers?"<br>"Faz um script de backup do banco e um de restauração."<br>"Como publico esse container no Render?" |
| **Trechos ou entregas afetadas** | `Entrega 2/Dockerfile`, `Entrega 2/docker-compose.yml`, `Entrega 2/infra/` (Dockerfiles, Caddy, `deploy/provisionar.sh`, `deploy/asa-turbo.service`, `monitoring/`, `scripts/backup.sh` e `restore.sh`, `loadtest/`), `Entrega 2/fly.toml`, `render.yaml` (raiz do repositório), `Entrega 2/DEPLOY.md`, `Entrega 2/scripts/smoke.sh`, `Entrega 2/scripts/reset_demo.sh`, `Entrega 2/docs/evidencias/` |


### Módulo do sistema 2 · Captura de documentos oficiais

| **Aluno(s) Responsável(veis)** | Bruno Eduardo da Silva Pinho |
| :--- | :--- |
| **Ferramenta utilizada** | Claude Code (Anthropic) |
| **Versão/modelo** | Claude Opus 5.5 |
| **Disciplina / Trabalho** | Inteligência Artificial · Projeto Interdisciplinar, Entrega 2 |
| **Finalidade de uso** | Apoio na organização dos documentos oficiais do ASA e da FECAP em chunks, na migração dos embeddings para a Cloudflare (bge-m3, 1024 dimensões), no versionamento dos documentos (cadastrar, nova versão, desativar) e na avaliação da recuperação do RAG. |
| ***Prompts* principais utilizados** | "Como divido os documentos em pedaços menores para o RAG?"<br>"Como gero embeddings com o bge-m3 pela Cloudflare?"<br>"Me ajuda a fazer a migração das tabelas para vetores de 1024."<br>"Como guardo versões diferentes do mesmo documento?"<br>"Como eu avalio se a busca está trazendo o documento certo?" |
| **Trechos ou entregas afetadas** | `Entrega 2/backend/app/rag/` (chunking, embeddings, recuperação), `Entrega 2/backend/app/services/documentos.py`, `Entrega 2/backend/app/api/admin.py` (rotas de documentos), `Entrega 2/data/migracao_entrega2_1024.sql`, `Entrega 2/infra/sql/`, `Entrega 2/ml/avaliar_rag.py`, `Entrega 2/ml/Avaliacao_RAG.ipynb` |

### Módulo do sistema 3 · Login

| **Aluno(s) Responsável(veis)** | Yanko Lee, Vivian Kaori Umaki |
| :--- | :--- |
| **Ferramenta utilizada** | Claude Code (Anthropic) |
| **Versão/modelo** | Claude Opus 5.5 |
| **Disciplina / Trabalho** | Inteligência Artificial · Projeto Interdisciplinar, Entrega 2 |
| **Finalidade de uso** | Apoio na tela de login com Supabase Auth, no controle de sessão no React, no redirecionamento por papel (estudante, atendente, administração) e nos botões de acesso de demonstração. |
| ***Prompts* principais utilizados** | "Como faço login com e-mail e senha usando o Supabase no React?"<br>"Como guardo a sessão do usuário num contexto?"<br>"Depois do login, como mando cada papel para sua tela?"<br>"Como bloqueio uma rota se o usuário não estiver logado?" |
| **Trechos ou entregas afetadas** | `Entrega 2/web/src/auth/` (`Login.jsx`, `FormLogin.jsx`, `SessaoContext.jsx`, `provedor.js`, `Login.module.css`), `Entrega 2/web/src/rotas/`, `Entrega 2/backend/app/core/auth.py` |

***Declaro que o uso acima descrito está em conformidade com o GUIA PARA O USO RESPONSÁVEL DE
INTELIGÊNCIA ARTIFICIAL NA FECAP e que o conteúdo final é de minha plena responsabilidade
autoral.***
