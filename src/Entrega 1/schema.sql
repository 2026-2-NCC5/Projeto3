-- =============================================================================
-- ASA - Agente para o Estudante | Schema do Banco de Dados (Supabase/Postgres)
-- Projeto Interdisciplinar - 5º CCOMP - FECAP - 2º SEMESTRE 2026
--
-- Como usar:
-- 1. Abra seu projeto em https://supabase.com/dashboard
-- 2. Vá em "SQL Editor" (ícone de terminal no menu lateral)
-- 3. Cole este arquivo inteiro e clique em "Run"
-- =============================================================================

-- Extensões necessárias
create extension if not exists "uuid-ossp";
create extension if not exists vector;          -- busca vetorial (pgvector) para o RAG
create extension if not exists pg_trgm;         -- busca textual auxiliar (fallback)

-- =============================================================================
-- 1. ENUMS (tipos controlados)
-- =============================================================================

create type papel_usuario as enum ('estudante', 'atendente', 'administrador', 'equipe_tecnica');
create type canal_conversa as enum ('chat_portal', 'app_mobile', 'presencial', 'email', 'whatsapp');
create type status_conversa as enum ('aberta', 'encerrada', 'encaminhada_humano');
create type remetente_mensagem as enum ('estudante', 'agente', 'atendente');
create type decisao_validacao as enum ('confirmado', 'ajustado', 'rejeitado', 'pendente');
create type prioridade_caso as enum ('baixa', 'media', 'alta', 'urgente');
create type status_matricula as enum ('regular', 'trancado', 'inadimplente', 'formado', 'evadido');
create type categoria_score as enum ('verde', 'amarelo', 'vermelho');

-- =============================================================================
-- 2. PERFIS DE USUÁRIO (estende auth.users do Supabase)
-- =============================================================================

create table perfis (
    id uuid primary key references auth.users(id) on delete cascade,
    papel papel_usuario not null default 'estudante',
    nome_completo text not null,
    email text not null unique,
    ativo boolean not null default true,
    criado_em timestamptz not null default now(),
    atualizado_em timestamptz not null default now()
);

comment on table perfis is 'Perfis de acesso: estudante, atendente ASA, administrador, equipe técnica (RF01)';

-- =============================================================================
-- 3. DADOS DO ESTUDANTE (RF02 - Perfil do estudante)
-- =============================================================================

create table estudantes (
    id uuid primary key references perfis(id) on delete cascade,
    ra text not null unique,
    curso text not null,
    semestre_atual int not null check (semestre_atual between 1 and 12),
    status status_matricula not null default 'regular',
    endereco_aproximado text,          -- ex: "Zona Sul - SP", nunca endereço exato (regra do edital)
    criado_em timestamptz not null default now(),
    atualizado_em timestamptz not null default now()
);

create table situacao_financeira (
    id uuid primary key default uuid_generate_v4(),
    estudante_id uuid not null references estudantes(id) on delete cascade,
    adimplente boolean not null default true,
    possui_acordo boolean not null default false,
    quantidade_pendencias int not null default 0,
    tipo_financiamento text,            -- 'FIES', 'PROUNI', 'particular', null
    atualizado_em timestamptz not null default now(),
    unique(estudante_id)
);

comment on table situacao_financeira is 'Nunca expor valores monetários exatos ao estudante sem autorização (regra do edital)';

create table situacao_academica (
    id uuid primary key default uuid_generate_v4(),
    estudante_id uuid not null references estudantes(id) on delete cascade,
    media_geral numeric(4,2),
    percentual_frequencia numeric(5,2),
    quantidade_reprovacoes int not null default 0,
    tendencia_desempenho text check (tendencia_desempenho in ('melhorando','estavel','piorando')),
    atualizado_em timestamptz not null default now(),
    unique(estudante_id)
);

create table matriculas (
    id uuid primary key default uuid_generate_v4(),
    estudante_id uuid not null references estudantes(id) on delete cascade,
    periodo_letivo text not null,        -- ex: '2026.2'
    status status_matricula not null,
    data_solicitacao timestamptz not null default now(),
    data_confirmacao timestamptz,
    observacoes text
);

-- =============================================================================
-- 4. BASE DE CONHECIMENTO (RF16) + CHUNKS VETORIZADOS (para o RAG)
-- =============================================================================

create table documentos_oficiais (
    id uuid primary key default uuid_generate_v4(),
    titulo text not null,
    categoria text not null,             -- 'regulamento', 'manual_aluno', 'financeiro', 'procedimento'
    fonte text not null,                 -- referência oficial, ex: 'Regulamento Acadêmico - Art. 27'
    versao int not null default 1,
    ativo boolean not null default true,
    data_atualizacao timestamptz not null default now(),
    criado_por uuid references perfis(id),
    criado_em timestamptz not null default now()
);

create table documentos_chunks (
    id uuid primary key default uuid_generate_v4(),
    documento_id uuid not null references documentos_oficiais(id) on delete cascade,
    ordem int not null,                  -- posição do chunk dentro do documento
    conteudo text not null,
    embedding vector(384),               -- 384 dimensões (compatível com MiniLM-L6-v2)
    criado_em timestamptz not null default now()
);

-- Índice para busca vetorial rápida por similaridade de cosseno
create index on documentos_chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- Função de busca vetorial (usada pelo agente para recuperar os trechos mais relevantes)
create or replace function buscar_chunks_similares(
    query_embedding vector(384),
    limite int default 3,
    limiar_similaridade float default 0.70
)
returns table (
    chunk_id uuid,
    documento_id uuid,
    conteudo text,
    similaridade float,
    titulo_documento text,
    fonte_documento text,
    data_atualizacao timestamptz
)
language sql stable
as $$
    select
        dc.id as chunk_id,
        dc.documento_id,
        dc.conteudo,
        1 - (dc.embedding <=> query_embedding) as similaridade,
        do_.titulo as titulo_documento,
        do_.fonte as fonte_documento,
        do_.data_atualizacao
    from documentos_chunks dc
    join documentos_oficiais do_ on do_.id = dc.documento_id
    where do_.ativo = true
      and 1 - (dc.embedding <=> query_embedding) >= limiar_similaridade
    order by dc.embedding <=> query_embedding
    limit limite;
$$;

-- =============================================================================
-- 5. CONVERSAS E MENSAGENS (histórico do chat)
-- =============================================================================

create table conversas (
    id uuid primary key default uuid_generate_v4(),
    estudante_id uuid not null references estudantes(id) on delete cascade,
    canal canal_conversa not null default 'chat_portal',
    status status_conversa not null default 'aberta',
    iniciada_em timestamptz not null default now(),
    encerrada_em timestamptz
);

create table mensagens (
    id uuid primary key default uuid_generate_v4(),
    conversa_id uuid not null references conversas(id) on delete cascade,
    remetente remetente_mensagem not null,
    conteudo text not null,
    criado_em timestamptz not null default now()
);

-- =============================================================================
-- 6. RESPOSTAS DO AGENTE + EVIDÊNCIAS (RF06 - Explicação e evidências)
-- =============================================================================

create table respostas_agente (
    id uuid primary key default uuid_generate_v4(),
    mensagem_id uuid not null references mensagens(id) on delete cascade,
    resposta_gerada text not null,
    confianca_score numeric(5,4) not null,   -- ex: 0.8421 (similaridade de cosseno do melhor chunk)
    versao_modelo text not null default 'v1.0',
    abstencao boolean not null default false, -- true quando o agente optou por não responder
    criado_em timestamptz not null default now()
);

create table resposta_evidencias (
    id uuid primary key default uuid_generate_v4(),
    resposta_id uuid not null references respostas_agente(id) on delete cascade,
    chunk_id uuid not null references documentos_chunks(id),
    similaridade numeric(5,4) not null,
    posicao_ranking int not null           -- 1 = mais relevante, 2 = segundo, etc.
);

-- =============================================================================
-- 7. VALIDAÇÃO HUMANA (RF08) E ENCAMINHAMENTOS (RF07/RF09)
-- =============================================================================

create table validacoes_humanas (
    id uuid primary key default uuid_generate_v4(),
    resposta_id uuid not null references respostas_agente(id) on delete cascade,
    atendente_id uuid references perfis(id),
    decisao decisao_validacao not null default 'pendente',
    justificativa text,
    criado_em timestamptz not null default now()
);

create table encaminhamentos (
    id uuid primary key default uuid_generate_v4(),
    conversa_id uuid not null references conversas(id) on delete cascade,
    motivo text not null,
    setor_destino text not null default 'ASA',
    prioridade prioridade_caso not null default 'media',
    atendente_responsavel uuid references perfis(id),
    status text not null default 'aberto' check (status in ('aberto','em_andamento','resolvido')),
    prazo timestamptz,
    criado_em timestamptz not null default now()
);

-- =============================================================================
-- 8. AUDITORIA (RF10) E FEEDBACK (RF17)
-- =============================================================================

create table auditoria_logs (
    id uuid primary key default uuid_generate_v4(),
    usuario_id uuid references perfis(id),
    acao text not null,                     -- ex: 'resposta_gerada', 'validacao_humana', 'login'
    entidade text not null,                 -- ex: 'respostas_agente', 'conversas'
    entidade_id uuid,
    detalhes jsonb,
    criado_em timestamptz not null default now()
);

create table feedback_respostas (
    id uuid primary key default uuid_generate_v4(),
    resposta_id uuid not null references respostas_agente(id) on delete cascade,
    estudante_id uuid not null references estudantes(id),
    avaliacao text not null check (avaliacao in ('util','nao_util')),
    comentario text,
    criado_em timestamptz not null default now()
);

-- =============================================================================
-- 9. EXTENSÃO OPCIONAL: Alertas de evasão (caso queiram demonstrar integração
--    com o Agente de Monitoramento como funcionalidade extra do edital)
-- =============================================================================

create table alertas_evasao (
    id uuid primary key default uuid_generate_v4(),
    estudante_id uuid not null references estudantes(id) on delete cascade,
    score_financeiro numeric(5,2),
    score_academico numeric(5,2),
    score_relacionamento numeric(5,2),
    score_geral numeric(5,2),
    categoria categoria_score not null,
    fatores jsonb,                          -- ex: {"faltas_recentes": true, "pendencia_financeira": false}
    criado_em timestamptz not null default now()
);

-- =============================================================================
-- 10. TRIGGERS: manter "atualizado_em" sempre em dia
-- =============================================================================

create or replace function trigger_set_atualizado_em()
returns trigger as $$
begin
    new.atualizado_em = now();
    return new;
end;
$$ language plpgsql;

create trigger set_atualizado_em_perfis before update on perfis
    for each row execute function trigger_set_atualizado_em();
create trigger set_atualizado_em_estudantes before update on estudantes
    for each row execute function trigger_set_atualizado_em();
create trigger set_atualizado_em_financeiro before update on situacao_financeira
    for each row execute function trigger_set_atualizado_em();
create trigger set_atualizado_em_academico before update on situacao_academica
    for each row execute function trigger_set_atualizado_em();

-- =============================================================================
-- 11. ÍNDICES ADICIONAIS DE PERFORMANCE
-- =============================================================================

create index idx_estudantes_ra on estudantes(ra);
create index idx_conversas_estudante on conversas(estudante_id);
create index idx_mensagens_conversa on mensagens(conversa_id);
create index idx_respostas_mensagem on respostas_agente(mensagem_id);
create index idx_auditoria_usuario on auditoria_logs(usuario_id);
create index idx_auditoria_criado_em on auditoria_logs(criado_em desc);
create index idx_documentos_chunks_doc on documentos_chunks(documento_id);
create index idx_alertas_estudante on alertas_evasao(estudante_id);

-- =============================================================================
-- 12. ROW LEVEL SECURITY (RLS) — obrigatório e ligado por padrão no Supabase
-- =============================================================================

alter table perfis enable row level security;
alter table estudantes enable row level security;
alter table situacao_financeira enable row level security;
alter table situacao_academica enable row level security;
alter table conversas enable row level security;
alter table mensagens enable row level security;
alter table respostas_agente enable row level security;
alter table validacoes_humanas enable row level security;
alter table auditoria_logs enable row level security;

-- Estudante só enxerga seus próprios dados
create policy "estudante_ve_proprio_perfil" on perfis
    for select using (auth.uid() = id);

create policy "estudante_ve_proprios_dados" on estudantes
    for select using (auth.uid() = id);

create policy "estudante_ve_propria_situacao_financeira" on situacao_financeira
    for select using (auth.uid() = estudante_id);

create policy "estudante_ve_propria_situacao_academica" on situacao_academica
    for select using (auth.uid() = estudante_id);

create policy "estudante_ve_proprias_conversas" on conversas
    for select using (auth.uid() = estudante_id);

create policy "estudante_ve_proprias_mensagens" on mensagens
    for select using (
        conversa_id in (select id from conversas where estudante_id = auth.uid())
    );

-- Atendentes e administradores têm acesso ampliado
create policy "atendente_admin_acesso_total_perfis" on perfis
    for all using (
        exists (
            select 1 from perfis p
            where p.id = auth.uid() and p.papel in ('atendente','administrador','equipe_tecnica')
        )
    );

create policy "atendente_admin_acesso_total_estudantes" on estudantes
    for all using (
        exists (
            select 1 from perfis p
            where p.id = auth.uid() and p.papel in ('atendente','administrador','equipe_tecnica')
        )
    );

-- =============================================================================
-- FIM DO SCHEMA
-- =============================================================================
