# Pendências conhecidas · v0.9.0

Lista honesta do que falta, do que foi contornado e do que não foi testado. Atualizada em 04/11/2026 (fechamento v0.9.1).

## Bloqueiam a publicação (dependem da equipe)

1. **Não há VM nem domínio.** Os scripts de `infra/deploy/` foram testados num container Ubuntu 24.04, sem systemd. O HTTPS automático, a unit systemd real e o `journalctl` só podem ser verificados numa VM com o DNS apontado.
2. **Faltam as chaves do Supabase gerenciado e da Cloudflare** nesta máquina. Por isso:
   - as migrations **002, 003 e 004** ainda não rodaram no Supabase real (a 001 e a base de conhecimento já estão lá);
   - os usuários de demonstração não foram criados lá (`seeds/criar_usuarios_demo.py`);
   - o `backup.sh --url` não foi testado contra o Supabase real;
   - o chat com embeddings bge-m3 não foi testado de ponta a ponta pelo backend novo. Localmente ele roda no fallback lexical.
3. **Dados reais no histórico do Git.** Os CSVs com 12.842 alunos continuam no commit `ee7c027`. A limpeza (`git filter-repo` + force push coordenado) está descrita em `docs/decisoes/0001-fase0.md` e não foi executada.

4. **Nenhum deploy em nuvem foi feito.** Não há CLI do Fly, do gcloud nem do Render nesta máquina. A imagem do container único foi testada localmente (`scripts/smoke.sh` com 8/8 OK e e2e 4/4 contra ela), mas a URL pública não existe ainda. Os passos estão em `DEPLOY.md`.
5. **O Blueprint do Render exige `git push`,** e a `main` local contém o commit `ee7c027` com os dados reais (ver item 3). Use o caminho A ou B do `DEPLOY.md` (imagem pronta), ou limpe o histórico antes.

## Modo de demonstração

- **As rotas `/demo/*` não estão em `docs/api-contract.yaml`.** São um atalho de apresentação que só existe com `DEMO_MODE=true`. A equipe precisa decidir se documenta no contrato.
- **O uso do chat que aparece no painel (30 dias) é simulado** e marcado como `sintetico` no repositório em memória. Os números de risco, fila e validações vêm dos seeds e do modelo.
- **A trajetória de 6 meses do caso de inadimplência foi construída** (parcelas e atraso crescentes) e pontuada mês a mês pelo modelo real. Os outros dois casos do topo são trajetórias dos seeds sem alteração. Também curado: os demais casos "urgentes" do seed aparecem como "alta", para os 3 ficarem no topo.
- **O estado da demo vive em memória:** reiniciar o processo, ou o Render dormir, volta tudo ao início. Isso é proposital.
- **No modo demo, o chat usa só o TF-IDF,** mesmo que haja chave da Cloudflare: o snapshot não tem vetores.

## Produto

4. **A qualidade do chat sem a Cloudflare é limitada.** O fallback lexical:
   - responde cerca de 11 de 14 perguntas do escopo;
   - às vezes prefere trechos curtos de "Condições" ou "Atendimento" ao passo a passo. Exemplo: o atestado de matrícula;
   - devolve o texto da base com prefixos como "Título - Condições:".

   Com embeddings, o comportamento muda e precisa ser reavaliado (`ml/avaliar_rag.py`).
5. **A resposta do chat é extrativa** (texto oficial, sem reescrita por LLM). Isso é seguro, porque nunca inventa, mas às vezes fica longa ou pouco natural.
6. **Limiares de risco:** a sessão de ML recomenda Amarelo ≥ 0,10 (recall de cerca de 89%). O contrato fixa 0,30/0,60 e continua assim. Mudar exige alterar `ModeloInfo.limiares` no contrato.
7. **O modelo é otimista.** A base é um retrato tirado depois do desfecho: a AUC de 0,91 no teste tende a cair com dados de corte reais. Detalhes em `ml/README.md`.
8. **Os scores dos 300 estudantes de demonstração** foram gerados pelo modelo v2 sobre features sintéticas. Ao recalcular pelo `/risco/inferir`, os números podem variar um pouco.
9. **O limite de mensagens do chat fica em memória** e vale por processo. Com mais de uma réplica do backend, ele precisa ir para o proxy ou para um Redis.
10. **`HEAD /health` responde 400** (rota não mapeada). O healthcheck do Docker usa GET e funciona; alguns monitores externos usam HEAD.

## Infra e operação

11. **cAdvisor:** com o containerd image store (padrão do Docker 29), o handler Docker do cAdvisor não identifica os containers. O painel junta os cgroups com os nomes de outra fonte (`infra/monitoring/prometheus.yml`). Funciona, mas é frágil a mudanças de versão.
12. **Proxy de login em produção:** a rota `/auth/v1` do Caddy só faz sentido na stack local. Em produção ela aponta para um host inexistente; isso é inofensivo, porque o front faz login direto no Supabase.
13. **Python 3.12 em vez de 3.11.** O artefato do ML usa XGBoost 3.4, que só existe para Python 3.12 ou mais novo. O backend subiu para 3.12; o CLAUDE.md foi atualizado.
14. **O teste de carga e o e2e gravam no banco de demonstração.** Antes de apresentar: `docker compose --profile local down -v && docker compose up -d`.

## Não testado

- Os fluxos completos em 390 px: o e2e roda em 1280 px; em 390 px só houve screenshots e axe.
- Firefox e WebKit, leitor de tela real, zoom de 200%.
- Service worker e uso offline do PWA.
- A instalação do PWA no celular.
- O deploy real, sem nenhuma etapa (ver item 1).
