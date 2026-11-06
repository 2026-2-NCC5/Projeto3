# ASA Turbo — contexto fixo do projeto

Leia este arquivo inteiro antes de qualquer tarefa. Ele vale para todas as sessões.

## O que estamos construindo
Projeto Interdisciplinar FECAP (5º CCOMP, 2026.2): agentes de IA para o ASA (Área do Sucesso Alvarista), com foco em reduzir evasão.

- **Escopo principal:** Agente para o Estudante, o chatbot "ASA Turbo" (RAG sobre base oficial).
- **Extensão:** Agente de Monitoramento de Risco de Evasão. O atendente do ASA usa o score para priorizar contatos. O estudante nunca vê o score.
- Entrega 2 vence em 06/11 às 23:59:56. Meta atual: **versão 0.9**, produto apresentável e vendável, com tudo funcionando de ponta a ponta.

## Fluxo que precisa funcionar (critério de aceite do enunciado)
Login → estudante conversa com o chat e recebe resposta com fontes e data de atualização (ou encaminhamento humano) → atendente abre a fila de risco, vê score, fatores, tendência e recomendação → confirma, ajusta ou rejeita com justificativa → tudo fica no histórico/auditoria → serviço publicado em nuvem com logs e métricas.

## Arquitetura (decidida)
| Pasta | Conteúdo |
|---|---|
| `backend/` | FastAPI (Python 3.11), roda em Docker. Valida JWT do Supabase, aplica RBAC, expõe a API. |
| `web/` | App responsivo instalável (PWA), HTML/CSS/JS com ES modules, **sem build step**. Servido pelo mesmo container ou por CDN. |
| `ml/` | Notebooks, scripts de treino, avaliação do RAG, artefatos do modelo (`ml/artifacts/`). |
| `infra/` | Dockerfile(s), docker-compose, Caddyfile, scripts de deploy, backup e teste de carga. |
| `seeds/` | Dados **fictícios** para demo e testes. |
| `data/` | Dados reais do ASA. **Está no .gitignore. Nunca versionar, nunca copiar para outras pastas.** |
| `docs/` | Contrato da API (`api-contract.yaml`), decisões, evidências. |

- Banco: Supabase (Postgres + pgvector + Auth). O schema base está em `schema.sql` (ou `infra/sql/`). Mudanças vão em migrations numeradas, nunca editando o que já rodou.
- Autenticação: Supabase Auth com e-mail e senha. O papel (`estudante`, `atendente`, `administrador`, `equipe_tecnica`) vem da tabela `perfis`. Menor privilégio em todos os endpoints.
- RAG: busca vetorial via `buscar_chunks_similares` (384 dimensões). Embeddings via Hugging Face Inference (`sentence-transformers/all-MiniLM-L6-v2`) com fallback automático para TF-IDF (`idf_table.json`) se a API falhar. Se a similaridade ficar abaixo do limiar, o agente **se abstém** e encaminha para humano. Nunca inventar procedimento, prazo ou regra.
- Modelo de risco: Regressão Logística baseline (AUC 0,82, Recall 77%). Faixas: Verde <30%, Amarelo 30–60%, Vermelho ≥60%. A v2 compara Random Forest e XGBoost.

## Regras inegociáveis (vêm do enunciado)
1. Nenhuma decisão punitiva automática. Todo resultado é apoio. Ação com impacto exige validação humana registrada com justificativa.
2. Privacidade (LGPD): sem dados pessoais reais no repositório, sem credenciais versionadas. `.env` fora do Git, com `.env.example` sem valores reais. Chave do Supabase no backend = **legacy `service_role` (`eyJ...`)**, nunca exposta no front.
3. Todo score mostra fatores, versão do modelo e data de atualização. Toda resposta do chat mostra fontes e data.
4. Geografia apenas aproximada (faixa de distância/região). Nunca endereço exato.
5. Solicitações legítimas ao ASA nunca viram fator punitivo no score.
6. Tudo gera auditoria: usuário, data/hora, versão, entrada, resultado, decisão humana.

## Padrões de código
- Python: tipado, módulos pequenos, `ruff` + `pytest`. Configuração por variáveis de ambiente (pydantic-settings). Logs estruturados em JSON.
- Front: sem framework pesado, sem build. Componentes simples em módulos ES. Acessível (contraste, foco visível, navegação por teclado, `aria-*`, leitor de tela).
- Commits pequenos e frequentes, mensagens no imperativo em português (`feat(web): fila de risco do atendente`).
- Ajuste pequeno = alterar só o arquivo necessário e dizer quais arquivos mudaram. Não reescrever o que não foi pedido.
- Cada sessão paralela só mexe na **sua pasta**. Se precisar mudar o contrato (`docs/api-contract.yaml`) ou outra pasta, pare e avise em vez de editar.

## Direção de design (o produto não pode ter "cara de IA")
Identidade FECAP: verde escuro institucional, fundo claro quente, muito respiro. Marca "ASA Turbo" (sandália alada com chama de turbina) em `web/assets/`.

**Fazer:**
- Interface de produto sério: hierarquia tipográfica clara, grade consistente, 1 cor de destaque (verde), semáforo Verde/Amarelo/Vermelho usado só para risco.
- Textos em português do Brasil, tom humano e objetivo, como um atendente atencioso. Ex.: "Não encontrei isso nos documentos oficiais. Quer que eu encaminhe para o ASA?"
- Estados reais em toda tela: carregando (esqueleto), vazio (com orientação do que fazer), erro (com ação de tentar de novo), offline.
- Densidade adequada ao uso: a fila do atendente é uma tabela/lista eficiente com filtros, não cards decorativos.

**Não fazer:**
- Gradientes roxo/azul, brilhos, glassmorphism, sombras exageradas, ícones de faíscas ou robôs.
- Emojis na interface. Saudações genéricas ("Olá! Sou seu assistente virtual incrível!").
- Textos em lorem ipsum, "Powered by AI", linguagem de marketing vazia.
- Cantos 100% arredondados em tudo, cards dentro de cards, tudo centralizado.
- Resposta do chat em blocos gigantes de markdown. Resposta curta, passo a passo numerado quando houver procedimento, fontes em rodapé discreto.

## Definição de pronto da v0.9
- [ ] Login funcionando com 3 perfis de demonstração (estudante, atendente, admin), com telas distintas por papel.
- [ ] Chat com contexto (últimas mensagens), fontes, data de atualização, abstenção, feedback útil/não útil e histórico salvo.
- [ ] Atendente: fila de risco filtrável, detalhe do aluno com score, fatores, tendência temporal e recomendação; validação humana com justificativa; histórico do caso.
- [ ] Admin: dashboard agregado (uso do chat, distribuição Verde/Amarelo/Vermelho, taxa de abstenção, feedback, ações) e gestão básica da base de conhecimento (cadastrar, versionar, desativar).
- [ ] Endpoint de inferência do risco integrado ao app, com versão do modelo.
- [ ] Docker + compose rodando local com um comando; deploy documentado em VM Linux com HTTPS.
- [ ] Logs JSON, `/health`, `/metrics`, script de teste de carga, script de backup/restauração.
- [ ] Testes automatizados básicos (backend e RAG) passando.
- [ ] `CHANGELOG.md` e tag `v0.9.0`.

**Fora do escopo desta fase:** relatório, Model Card, banner, PDI, documento de extensão. Os scripts só precisam **gerar os números e figuras** (JSON/PNG em `ml/artifacts/` e `docs/evidencias/`) para esses documentos serem escritos depois.
