-- =============================================================================
-- 002 · Ajustes para o contrato da API v0.9 (docs/api-contract.yaml)
-- =============================================================================
-- Pré-requisito: 001_schema_base.sql (ou o banco atual do Supabase).
-- IDEMPOTENTE: pode rodar mais de uma vez (if not exists / drop ... if exists).
--
-- O que faz:
--   1. Funções auxiliares de papel (security definer). Corrige a recursão
--      infinita da policy "atendente_admin_acesso_total_perfis" do 001, que
--      consultava perfis dentro de uma policy de perfis.
--   2. estudantes deixa de exigir login: id próprio + perfil_id opcional.
--      Necessário para a fila de risco ter estudantes que nunca usaram o chat.
--   3. Risco: estudante_features, scores_risco (histórico mensal),
--      casos_risco (status, prioridade, prazo), validacoes_caso (decisão
--      humana com justificativa, append-only), eventos_caso, contatos_asa.
--   4. Base de conhecimento: documentos_versoes + campos de desativação.
--   5. Colunas novas em conversas, respostas_agente, auditoria_logs,
--      encaminhamentos.
--   6. RLS em TODAS as tabelas. O estudante nunca enxerga dados de risco.
--   7. View vw_fila_risco (usada por GET /casos).
--
-- O backend usa a chave service_role (ignora RLS). As policies abaixo são
-- defesa em profundidade e protegem qualquer acesso direto com JWT de usuário.
-- =============================================================================

begin;

-- =============================================================================
-- 0. ENUMS NOVOS
-- =============================================================================
do $$ begin
    create type status_caso as enum ('novo', 'em_acompanhamento', 'contatado', 'resolvido', 'arquivado');
exception when duplicate_object then null; end $$;

do $$ begin
    create type faixa_distancia as enum ('ate_5km', '5_15km', '15_30km', 'acima_30km');
exception when duplicate_object then null; end $$;

do $$ begin
    -- Regra 5: só 'contato_ativo' (iniciado pelo ASA) pode alimentar o modelo.
    -- 'solicitacao_estudante' (o estudante procurou o ASA) NUNCA vira fator punitivo.
    create type origem_contato as enum ('solicitacao_estudante', 'contato_ativo');
exception when duplicate_object then null; end $$;

-- =============================================================================
-- 1. FUNÇÕES AUXILIARES DE PAPEL
-- =============================================================================
-- security definer: leem perfis/estudantes ignorando RLS, o que evita recursão
-- quando usadas dentro de policies dessas mesmas tabelas.

create or replace function public.papel_atual()
returns papel_usuario
language sql stable security definer
set search_path = public
as $$
    select papel from perfis where id = auth.uid() and ativo
$$;

create or replace function public.eh_equipe_asa()
returns boolean
language sql stable security definer
set search_path = public
as $$
    select coalesce(public.papel_atual() in ('atendente', 'administrador'), false)
$$;

create or replace function public.eh_admin()
returns boolean
language sql stable security definer
set search_path = public
as $$
    select coalesce(public.papel_atual() = 'administrador', false)
$$;

-- =============================================================================
-- 2. ESTUDANTES SEM LOGIN OBRIGATÓRIO
-- =============================================================================
alter table estudantes drop constraint if exists estudantes_id_fkey;
alter table estudantes alter column id set default uuid_generate_v4();

alter table estudantes add column if not exists perfil_id uuid;
alter table estudantes add column if not exists nome_exibicao text;
alter table estudantes add column if not exists faixa_distancia faixa_distancia;
alter table estudantes add column if not exists regiao text;   -- ex.: 'Zona Sul - SP'. Nunca endereço exato (regra 4)

do $$ begin
    alter table estudantes add constraint estudantes_perfil_id_fkey
        foreign key (perfil_id) references perfis(id) on delete set null;
exception when duplicate_object then null; end $$;

create unique index if not exists ux_estudantes_perfil on estudantes(perfil_id) where perfil_id is not null;

-- Quem já existia tinha id = perfis.id
update estudantes e set perfil_id = e.id
 where e.perfil_id is null
   and exists (select 1 from perfis p where p.id = e.id);

comment on column estudantes.perfil_id is 'Login do estudante (perfis.id). Nulo para quem nunca acessou o app.';
comment on column estudantes.nome_exibicao is 'Nome mostrado ao atendente. Nos seeds, sempre fictício.';

create or replace function public.meu_estudante_id()
returns uuid
language sql stable security definer
set search_path = public
as $$
    select id from estudantes where perfil_id = auth.uid()
$$;

-- =============================================================================
-- 3. MONITORAMENTO DE RISCO
-- =============================================================================

-- 3.1 Snapshot mensal das features, no formato do modelo (base_unificada)
create table if not exists estudante_features (
    id uuid primary key default uuid_generate_v4(),
    estudante_id uuid not null references estudantes(id) on delete cascade,
    competencia date not null,                       -- 1º dia do mês de referência
    -- numéricas
    tempo_de_curso numeric,
    idade int,
    mora_sp_capital boolean,
    total_parcelas int,
    pct_parcelas_em_aberto numeric,
    pct_parcelas_acordo numeric,
    atraso_medio_dias numeric,
    valor_total_periodo numeric,
    media_notas numeric,
    media_assiduidade numeric,
    pct_reprovacao numeric,
    tendencia_notas numeric,
    tendencia_assiduidade numeric,
    total_semestres int,
    total_contatos int,               -- ATENÇÃO regra 5: só contatos ativos do ASA
    dias_desde_ultimo_contato int,
    -- categóricas (rótulos iguais aos da base do modelo)
    forma_ingresso text,
    grau_academico text,
    turno text,
    estado_civil text,                -- sensível: nunca exibido como fator
    sexo text,                        -- sensível: nunca exibido como fator
    tem_bolsa boolean,
    fonte text not null default 'seed', -- 'seed' | 'totvs' | 'manual'
    criado_em timestamptz not null default now(),
    unique (estudante_id, competencia)
);

-- 3.2 Score mensal (histórico para tendência)
create table if not exists scores_risco (
    id uuid primary key default uuid_generate_v4(),
    estudante_id uuid not null references estudantes(id) on delete cascade,
    competencia date not null,
    probabilidade numeric(5,4) not null check (probabilidade between 0 and 1),  -- score geral
    score_financeiro numeric(5,4) check (score_financeiro between 0 and 1),
    score_academico numeric(5,4) check (score_academico between 0 and 1),
    score_relacionamento numeric(5,4) check (score_relacionamento between 0 and 1),
    categoria categoria_score not null,             -- Verde < 0,30 <= Amarelo < 0,60 <= Vermelho
    fatores jsonb not null default '[]'::jsonb,     -- [{codigo, descricao, dimensao, direcao, peso}]
    recomendacao text,
    versao_modelo text not null,
    calculado_em timestamptz not null default now(),
    unique (estudante_id, competencia, versao_modelo)
);
comment on table scores_risco is 'Apoio à decisão. Nunca gera ação punitiva automática. Invisível ao estudante.';

-- 3.3 Caso de acompanhamento (um por estudante)
create table if not exists casos_risco (
    id uuid primary key default uuid_generate_v4(),
    estudante_id uuid not null unique references estudantes(id) on delete cascade,
    status status_caso not null default 'novo',
    prioridade prioridade_caso not null default 'media',
    prazo date,
    atendente_responsavel uuid references perfis(id) on delete set null,
    score_atual_id uuid references scores_risco(id) on delete set null,
    categoria_vigente categoria_score,               -- categoria após validação humana (null = a do modelo)
    criado_em timestamptz not null default now(),
    atualizado_em timestamptz not null default now()
);

-- 3.4 Validação humana do caso (append-only: sem policy de update/delete)
create table if not exists validacoes_caso (
    id uuid primary key default uuid_generate_v4(),
    caso_id uuid not null references casos_risco(id) on delete cascade,
    score_id uuid references scores_risco(id) on delete set null,
    atendente_id uuid not null references perfis(id),
    decisao decisao_validacao not null check (decisao <> 'pendente'),
    justificativa text not null check (char_length(btrim(justificativa)) >= 20),
    categoria_ajustada categoria_score,
    prioridade_definida prioridade_caso,
    prazo_definido date,
    versao_modelo text not null,
    criado_em timestamptz not null default now(),
    check (decisao <> 'ajustado' or categoria_ajustada is not null)
);

-- 3.5 Linha do tempo do caso (mudanças de status, responsável, prazo)
create table if not exists eventos_caso (
    id uuid primary key default uuid_generate_v4(),
    caso_id uuid not null references casos_risco(id) on delete cascade,
    usuario_id uuid references perfis(id),
    tipo text not null,                 -- 'criado' | 'status' | 'prioridade' | 'prazo' | 'responsavel' | 'validacao'
    de text,
    para text,
    detalhes jsonb,
    criado_em timestamptz not null default now()
);

-- 3.6 Contatos e atendimentos do ASA
create table if not exists contatos_asa (
    id uuid primary key default uuid_generate_v4(),
    estudante_id uuid not null references estudantes(id) on delete cascade,
    atendente_id uuid references perfis(id) on delete set null,
    origem origem_contato not null,
    canal canal_conversa not null default 'presencial',
    motivo text not null,
    resumo text,
    resultado text,
    ocorrido_em timestamptz not null default now(),
    criado_em timestamptz not null default now()
);
comment on column contatos_asa.origem is 'Regra 5: solicitacao_estudante nunca alimenta o score de risco.';

-- =============================================================================
-- 4. BASE DE CONHECIMENTO: VERSÕES E DESATIVAÇÃO
-- =============================================================================
alter table documentos_oficiais add column if not exists desativado_em timestamptz;
alter table documentos_oficiais add column if not exists desativado_por uuid references perfis(id);
alter table documentos_oficiais add column if not exists motivo_desativacao text;

create table if not exists documentos_versoes (
    id uuid primary key default uuid_generate_v4(),
    documento_id uuid not null references documentos_oficiais(id) on delete cascade,
    versao int not null,
    titulo text not null,
    categoria text not null,
    fonte text not null,
    conteudo text not null,
    data_atualizacao timestamptz not null,
    alterado_por uuid references perfis(id),
    motivo text,
    criado_em timestamptz not null default now(),
    unique (documento_id, versao)
);

-- Registra a versão vigente de cada documento já existente
insert into documentos_versoes (documento_id, versao, titulo, categoria, fonte, conteudo, data_atualizacao, alterado_por, motivo)
select d.id, d.versao, d.titulo, d.categoria, d.fonte,
       coalesce((select string_agg(c.conteudo, E'\n\n' order by c.ordem)
                   from documentos_chunks c where c.documento_id = d.id), ''),
       d.data_atualizacao, d.criado_por, 'Versão inicial (migração 002)'
  from documentos_oficiais d
on conflict (documento_id, versao) do nothing;

-- =============================================================================
-- 5. COLUNAS NOVAS EM TABELAS EXISTENTES
-- =============================================================================
alter table conversas add column if not exists titulo text;
alter table conversas add column if not exists atualizado_em timestamptz not null default now();

alter table respostas_agente add column if not exists latencia_ms int;
alter table respostas_agente add column if not exists modelo_embedding text;

alter table auditoria_logs add column if not exists request_id text;
alter table auditoria_logs add column if not exists papel papel_usuario;
alter table auditoria_logs add column if not exists versao text;          -- versão do app/modelo
alter table auditoria_logs add column if not exists entrada jsonb;
alter table auditoria_logs add column if not exists resultado jsonb;

alter table encaminhamentos add column if not exists resposta_id uuid references respostas_agente(id) on delete set null;

-- =============================================================================
-- 6. TRIGGERS E ÍNDICES
-- =============================================================================
drop trigger if exists set_atualizado_em_casos on casos_risco;
create trigger set_atualizado_em_casos before update on casos_risco
    for each row execute function trigger_set_atualizado_em();

drop trigger if exists set_atualizado_em_conversas on conversas;
create trigger set_atualizado_em_conversas before update on conversas
    for each row execute function trigger_set_atualizado_em();

create index if not exists idx_features_estudante on estudante_features(estudante_id, competencia desc);
create index if not exists idx_scores_estudante on scores_risco(estudante_id, competencia desc);
create index if not exists idx_scores_categoria on scores_risco(categoria);
create index if not exists idx_casos_status_prioridade on casos_risco(status, prioridade);
create index if not exists idx_validacoes_caso on validacoes_caso(caso_id, criado_em desc);
create index if not exists idx_eventos_caso on eventos_caso(caso_id, criado_em desc);
create index if not exists idx_contatos_estudante on contatos_asa(estudante_id, ocorrido_em desc);
create index if not exists idx_doc_versoes on documentos_versoes(documento_id, versao desc);
create index if not exists idx_feedback_resposta on feedback_respostas(resposta_id);
create index if not exists idx_estudantes_nome_trgm on estudantes using gin (nome_exibicao gin_trgm_ops);

-- =============================================================================
-- 7. ROW LEVEL SECURITY
-- =============================================================================
alter table perfis               enable row level security;
alter table estudantes           enable row level security;
alter table situacao_financeira  enable row level security;
alter table situacao_academica   enable row level security;
alter table matriculas           enable row level security;
alter table documentos_oficiais  enable row level security;
alter table documentos_chunks    enable row level security;
alter table documentos_versoes   enable row level security;
alter table conversas            enable row level security;
alter table mensagens            enable row level security;
alter table respostas_agente     enable row level security;
alter table resposta_evidencias  enable row level security;
alter table validacoes_humanas   enable row level security;
alter table encaminhamentos      enable row level security;
alter table auditoria_logs       enable row level security;
alter table feedback_respostas   enable row level security;
alter table alertas_evasao       enable row level security;
alter table estudante_features   enable row level security;
alter table scores_risco         enable row level security;
alter table casos_risco          enable row level security;
alter table validacoes_caso      enable row level security;
alter table eventos_caso         enable row level security;
alter table contatos_asa         enable row level security;

-- ---- perfis (substitui a policy recursiva do 001)
drop policy if exists "atendente_admin_acesso_total_perfis" on perfis;
drop policy if exists "estudante_ve_proprio_perfil" on perfis;
drop policy if exists "perfis_proprio" on perfis;
drop policy if exists "perfis_equipe_le" on perfis;
drop policy if exists "perfis_admin_gerencia" on perfis;
create policy "perfis_proprio" on perfis for select using (id = auth.uid());
create policy "perfis_equipe_le" on perfis for select using (public.eh_equipe_asa());
create policy "perfis_admin_gerencia" on perfis for all using (public.eh_admin()) with check (public.eh_admin());

-- ---- estudantes
drop policy if exists "atendente_admin_acesso_total_estudantes" on estudantes;
drop policy if exists "estudante_ve_proprios_dados" on estudantes;
drop policy if exists "estudantes_proprio" on estudantes;
drop policy if exists "estudantes_equipe" on estudantes;
create policy "estudantes_proprio" on estudantes for select using (perfil_id = auth.uid());
create policy "estudantes_equipe" on estudantes for all using (public.eh_equipe_asa()) with check (public.eh_equipe_asa());

-- ---- situação financeira / acadêmica / matrículas
drop policy if exists "estudante_ve_propria_situacao_financeira" on situacao_financeira;
drop policy if exists "sit_fin_proprio" on situacao_financeira;
drop policy if exists "sit_fin_equipe" on situacao_financeira;
create policy "sit_fin_proprio" on situacao_financeira for select using (estudante_id = public.meu_estudante_id());
create policy "sit_fin_equipe" on situacao_financeira for select using (public.eh_equipe_asa());

drop policy if exists "estudante_ve_propria_situacao_academica" on situacao_academica;
drop policy if exists "sit_acad_proprio" on situacao_academica;
drop policy if exists "sit_acad_equipe" on situacao_academica;
create policy "sit_acad_proprio" on situacao_academica for select using (estudante_id = public.meu_estudante_id());
create policy "sit_acad_equipe" on situacao_academica for select using (public.eh_equipe_asa());

drop policy if exists "matriculas_proprio" on matriculas;
drop policy if exists "matriculas_equipe" on matriculas;
create policy "matriculas_proprio" on matriculas for select using (estudante_id = public.meu_estudante_id());
create policy "matriculas_equipe" on matriculas for select using (public.eh_equipe_asa());

-- ---- base de conhecimento: leitura só do que está ativo; gestão só admin
drop policy if exists "docs_le_ativos" on documentos_oficiais;
drop policy if exists "docs_admin" on documentos_oficiais;
create policy "docs_le_ativos" on documentos_oficiais for select to authenticated using (ativo);
create policy "docs_admin" on documentos_oficiais for all using (public.eh_admin()) with check (public.eh_admin());

drop policy if exists "chunks_le_ativos" on documentos_chunks;
drop policy if exists "chunks_admin" on documentos_chunks;
create policy "chunks_le_ativos" on documentos_chunks for select to authenticated
    using (exists (select 1 from documentos_oficiais d where d.id = documento_id and d.ativo));
create policy "chunks_admin" on documentos_chunks for all using (public.eh_admin()) with check (public.eh_admin());

drop policy if exists "doc_versoes_admin" on documentos_versoes;
create policy "doc_versoes_admin" on documentos_versoes for all using (public.eh_admin()) with check (public.eh_admin());

-- ---- chat: o estudante vê só o que é dele; a equipe lê para atender encaminhamentos
drop policy if exists "estudante_ve_proprias_conversas" on conversas;
drop policy if exists "conversas_proprio" on conversas;
drop policy if exists "conversas_proprio_insere" on conversas;
drop policy if exists "conversas_equipe" on conversas;
create policy "conversas_proprio" on conversas for select using (estudante_id = public.meu_estudante_id());
create policy "conversas_proprio_insere" on conversas for insert with check (estudante_id = public.meu_estudante_id());
create policy "conversas_equipe" on conversas for select using (public.eh_equipe_asa());

drop policy if exists "estudante_ve_proprias_mensagens" on mensagens;
drop policy if exists "mensagens_proprio" on mensagens;
drop policy if exists "mensagens_equipe" on mensagens;
create policy "mensagens_proprio" on mensagens for select
    using (conversa_id in (select id from conversas where estudante_id = public.meu_estudante_id()));
create policy "mensagens_equipe" on mensagens for select using (public.eh_equipe_asa());

drop policy if exists "respostas_proprio" on respostas_agente;
drop policy if exists "respostas_equipe" on respostas_agente;
create policy "respostas_proprio" on respostas_agente for select
    using (mensagem_id in (select m.id from mensagens m join conversas c on c.id = m.conversa_id
                            where c.estudante_id = public.meu_estudante_id()));
create policy "respostas_equipe" on respostas_agente for select using (public.eh_equipe_asa());

drop policy if exists "evidencias_proprio" on resposta_evidencias;
drop policy if exists "evidencias_equipe" on resposta_evidencias;
create policy "evidencias_proprio" on resposta_evidencias for select
    using (resposta_id in (select r.id from respostas_agente r join mensagens m on m.id = r.mensagem_id
                            join conversas c on c.id = m.conversa_id
                            where c.estudante_id = public.meu_estudante_id()));
create policy "evidencias_equipe" on resposta_evidencias for select using (public.eh_equipe_asa());

drop policy if exists "feedback_proprio_le" on feedback_respostas;
drop policy if exists "feedback_proprio_insere" on feedback_respostas;
drop policy if exists "feedback_admin" on feedback_respostas;
create policy "feedback_proprio_le" on feedback_respostas for select using (estudante_id = public.meu_estudante_id());
create policy "feedback_proprio_insere" on feedback_respostas for insert with check (estudante_id = public.meu_estudante_id());
create policy "feedback_admin" on feedback_respostas for select using (public.eh_admin());

drop policy if exists "validacoes_humanas_equipe" on validacoes_humanas;
create policy "validacoes_humanas_equipe" on validacoes_humanas for all using (public.eh_equipe_asa()) with check (public.eh_equipe_asa());

drop policy if exists "encaminhamentos_proprio" on encaminhamentos;
drop policy if exists "encaminhamentos_equipe" on encaminhamentos;
create policy "encaminhamentos_proprio" on encaminhamentos for select
    using (conversa_id in (select id from conversas where estudante_id = public.meu_estudante_id()));
create policy "encaminhamentos_equipe" on encaminhamentos for all using (public.eh_equipe_asa()) with check (public.eh_equipe_asa());

-- ---- auditoria: leitura só admin; escrita só pelo backend (service_role)
drop policy if exists "auditoria_admin_le" on auditoria_logs;
create policy "auditoria_admin_le" on auditoria_logs for select using (public.eh_admin());

-- ---- risco: SÓ atendente e administrador. Nenhuma policy para estudante.
drop policy if exists "alertas_equipe" on alertas_evasao;
create policy "alertas_equipe" on alertas_evasao for select using (public.eh_equipe_asa());

drop policy if exists "features_equipe" on estudante_features;
create policy "features_equipe" on estudante_features for select using (public.eh_equipe_asa());

drop policy if exists "scores_equipe" on scores_risco;
create policy "scores_equipe" on scores_risco for select using (public.eh_equipe_asa());

drop policy if exists "casos_equipe_le" on casos_risco;
drop policy if exists "casos_equipe_atualiza" on casos_risco;
create policy "casos_equipe_le" on casos_risco for select using (public.eh_equipe_asa());
create policy "casos_equipe_atualiza" on casos_risco for update using (public.eh_equipe_asa()) with check (public.eh_equipe_asa());

drop policy if exists "validacoes_caso_equipe_le" on validacoes_caso;
drop policy if exists "validacoes_caso_equipe_insere" on validacoes_caso;
create policy "validacoes_caso_equipe_le" on validacoes_caso for select using (public.eh_equipe_asa());
create policy "validacoes_caso_equipe_insere" on validacoes_caso for insert
    with check (public.eh_equipe_asa() and atendente_id = auth.uid());

drop policy if exists "eventos_caso_equipe_le" on eventos_caso;
drop policy if exists "eventos_caso_equipe_insere" on eventos_caso;
create policy "eventos_caso_equipe_le" on eventos_caso for select using (public.eh_equipe_asa());
create policy "eventos_caso_equipe_insere" on eventos_caso for insert
    with check (public.eh_equipe_asa() and usuario_id = auth.uid());

drop policy if exists "contatos_equipe" on contatos_asa;
create policy "contatos_equipe" on contatos_asa for all using (public.eh_equipe_asa()) with check (public.eh_equipe_asa());

-- =============================================================================
-- 8. VIEW DA FILA DE RISCO (GET /casos)
-- =============================================================================
-- security_invoker: a view respeita o RLS de quem consulta (Postgres 15+).
drop view if exists vw_fila_risco;
create view vw_fila_risco with (security_invoker = true) as
with ultimo as (
    select distinct on (s.estudante_id) s.*
      from scores_risco s
     order by s.estudante_id, s.competencia desc, s.calculado_em desc
),
anterior as (
    -- score da competência imediatamente anterior, mesma versão de modelo
    select distinct on (s.estudante_id) s.estudante_id, s.probabilidade
      from scores_risco s
      join ultimo u on u.estudante_id = s.estudante_id
                   and u.versao_modelo = s.versao_modelo
                   and s.competencia < u.competencia
     order by s.estudante_id, s.competencia desc
),
ultima_validacao as (
    select distinct on (v.caso_id) v.caso_id, v.decisao, v.criado_em
      from validacoes_caso v
     order by v.caso_id, v.criado_em desc
)
select
    e.id                         as estudante_id,
    e.ra,
    e.nome_exibicao,
    e.curso,
    e.semestre_atual,
    e.faixa_distancia,
    e.regiao,
    u.id                         as score_id,
    u.probabilidade              as score_geral,
    u.score_financeiro,
    u.score_academico,
    u.score_relacionamento,
    u.categoria                  as categoria_modelo,
    coalesce(c.categoria_vigente, u.categoria) as categoria,
    round(u.probabilidade - a.probabilidade, 4) as variacao,
    case
        when a.probabilidade is null then 'estavel'
        when u.probabilidade - a.probabilidade >= 0.05 then 'subindo'
        when u.probabilidade - a.probabilidade <= -0.05 then 'caindo'
        else 'estavel'
    end                          as tendencia,
    u.versao_modelo,
    u.competencia,
    u.calculado_em               as atualizado_em,
    c.id                         as caso_id,
    c.status,
    c.prioridade,
    c.prazo,
    c.atendente_responsavel,
    v.decisao                    as ultima_decisao,
    v.criado_em                  as ultima_validacao_em
from estudantes e
join ultimo u on u.estudante_id = e.id
left join anterior a on a.estudante_id = e.id
left join casos_risco c on c.estudante_id = e.id
left join ultima_validacao v on v.caso_id = c.id;

comment on view vw_fila_risco is 'Fila do atendente: último score, tendência e situação do caso. Invisível ao estudante.';

commit;
