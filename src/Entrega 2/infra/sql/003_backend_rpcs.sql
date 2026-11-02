-- =============================================================================
-- 003 · Funções e views usadas pelo backend FastAPI (sessão backend)
-- =============================================================================
-- Pré-requisito: 001 + 002. IDEMPOTENTE (create or replace / if not exists).
--
-- O que faz:
--   1. unaccent + coluna de busca normalizada na fila (busca por nome/RA sem acento).
--   2. documentos_chunks.ativo: uma nova versão do documento DESATIVA os chunks
--      antigos em vez de apagá-los (resposta_evidencias continua apontando para
--      eles: "respostas antigas continuam citando a fonte"). buscar_chunks_similares
--      passa a ignorar chunks inativos (mesma assinatura).
--   3. vw_documentos_resumo (contagem de chunks / pendentes de embedding).
--   4. RPCs transacionais: chat, feedback, validação humana, score, documentos e
--      dashboard. Erros de negócio usam SQLSTATE PT404/PT409, que o PostgREST
--      converte em HTTP 404/409.
--   5. SEGURANÇA: as RPCs só podem ser chamadas pelo service_role (backend).
--      anon/authenticated perdem o EXECUTE (por padrão o Postgres dá a PUBLIC).
-- =============================================================================

begin;

create extension if not exists unaccent;

-- -----------------------------------------------------------------------------
-- 1. Chunks versionados
-- -----------------------------------------------------------------------------
alter table documentos_chunks add column if not exists ativo boolean not null default true;
create index if not exists idx_chunks_ativos on documentos_chunks(documento_id) where ativo;

create or replace function buscar_chunks_similares(
    query_embedding vector(1024),
    limite int default 3,
    limiar_similaridade float default 0.0
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
    select dc.id, dc.documento_id, dc.conteudo,
           1 - (dc.embedding <=> query_embedding) as similaridade,
           d.titulo, d.fonte, d.data_atualizacao
      from documentos_chunks dc
      join documentos_oficiais d on d.id = dc.documento_id
     where d.ativo and dc.ativo and dc.embedding is not null
       and 1 - (dc.embedding <=> query_embedding) >= limiar_similaridade
     order by dc.embedding <=> query_embedding
     limit limite;
$$;

-- -----------------------------------------------------------------------------
-- 2. Views
-- -----------------------------------------------------------------------------
drop view if exists vw_fila_risco_busca;
create view vw_fila_risco_busca with (security_invoker = true) as
select f.*,
       lower(unaccent(coalesce(f.nome_exibicao, '') || ' ' || f.ra)) as busca
  from vw_fila_risco f;
comment on view vw_fila_risco_busca is 'vw_fila_risco + coluna "busca" (nome e RA sem acento) para GET /casos.';

drop view if exists vw_documentos_resumo;
create view vw_documentos_resumo with (security_invoker = true) as
select d.id, d.titulo, d.categoria, d.fonte, d.versao, d.ativo, d.data_atualizacao,
       d.desativado_em, d.motivo_desativacao, d.criado_em,
       count(c.id) filter (where c.ativo)                            as total_chunks,
       count(c.id) filter (where c.ativo and c.embedding is null)    as chunks_sem_embedding,
       lower(unaccent(d.titulo || ' ' || d.fonte))                   as busca
  from documentos_oficiais d
  left join documentos_chunks c on c.documento_id = d.id
 group by d.id;

-- -----------------------------------------------------------------------------
-- 3. Chat: grava pergunta, resposta, evidências e encaminhamento numa transação
-- -----------------------------------------------------------------------------
-- p: {estudante_id, conversa_id?, titulo, pergunta, resposta, confianca, abstencao,
--     versao_modelo, modelo_embedding, latencia_ms, resposta_id?, evidencias:[{chunk_id,similaridade,posicao}],
--     encaminhar, motivo_encaminhamento, prazo_encaminhamento}
create or replace function registrar_resposta_chat(p jsonb)
returns jsonb
language plpgsql
as $$
declare
    v_conversa uuid := nullif(p->>'conversa_id', '')::uuid;
    v_estudante uuid := (p->>'estudante_id')::uuid;
    v_msg_estudante uuid;
    v_msg_agente uuid;
    v_resposta uuid := coalesce(nullif(p->>'resposta_id', '')::uuid, uuid_generate_v4());
    v_enc encaminhamentos%rowtype;
    v_ev jsonb;
begin
    if v_conversa is null then
        insert into conversas (estudante_id, canal, status, titulo)
        values (v_estudante, 'chat_portal', 'aberta', left(coalesce(p->>'titulo', 'Conversa'), 80))
        returning id into v_conversa;
    else
        perform 1 from conversas where id = v_conversa and estudante_id = v_estudante for update;
        if not found then
            raise exception 'conversa não encontrada' using errcode = 'PT404';
        end if;
    end if;

    insert into mensagens (conversa_id, remetente, conteudo)
    values (v_conversa, 'estudante', p->>'pergunta') returning id into v_msg_estudante;

    insert into mensagens (conversa_id, remetente, conteudo, criado_em)
    values (v_conversa, 'agente', p->>'resposta', clock_timestamp()) returning id into v_msg_agente;

    insert into respostas_agente (id, mensagem_id, resposta_gerada, confianca_score, versao_modelo,
                                  abstencao, modelo_embedding, latencia_ms)
    values (v_resposta, v_msg_agente, p->>'resposta', (p->>'confianca')::numeric,
            p->>'versao_modelo', (p->>'abstencao')::boolean, p->>'modelo_embedding',
            nullif(p->>'latencia_ms', '')::int);

    for v_ev in select * from jsonb_array_elements(coalesce(p->'evidencias', '[]'::jsonb)) loop
        insert into resposta_evidencias (resposta_id, chunk_id, similaridade, posicao_ranking)
        values (v_resposta, (v_ev->>'chunk_id')::uuid, (v_ev->>'similaridade')::numeric, (v_ev->>'posicao')::int);
    end loop;

    if coalesce((p->>'encaminhar')::boolean, false) then
        -- reaproveita encaminhamento ainda aberto da mesma conversa
        select * into v_enc from encaminhamentos
         where conversa_id = v_conversa and status in ('aberto', 'em_andamento')
         order by criado_em desc limit 1;
        if not found then
            insert into encaminhamentos (conversa_id, resposta_id, motivo, setor_destino, prioridade, status, prazo)
            values (v_conversa, v_resposta, coalesce(p->>'motivo_encaminhamento', 'Abstenção do agente'),
                    'ASA', 'media', 'aberto', nullif(p->>'prazo_encaminhamento', '')::timestamptz)
            returning * into v_enc;
        end if;
        update conversas set status = 'encaminhada_humano', atualizado_em = now() where id = v_conversa;
    else
        update conversas set atualizado_em = now() where id = v_conversa;
    end if;

    return jsonb_build_object(
        'conversa_id', v_conversa,
        'resposta_id', v_resposta,
        'mensagem_id', v_msg_agente,
        'encaminhamento', case when v_enc.id is null then null else jsonb_build_object(
            'id', v_enc.id, 'status', v_enc.status, 'setor_destino', v_enc.setor_destino, 'prazo', v_enc.prazo) end
    );
end;
$$;

-- Feedback: reenviar substitui a avaliação anterior do mesmo estudante
create or replace function salvar_feedback(p_resposta uuid, p_estudante uuid, p_avaliacao text, p_comentario text)
returns jsonb
language plpgsql
as $$
declare
    v feedback_respostas%rowtype;
begin
    perform 1 from respostas_agente r
      join mensagens m on m.id = r.mensagem_id
      join conversas c on c.id = m.conversa_id
     where r.id = p_resposta and c.estudante_id = p_estudante;
    if not found then
        raise exception 'resposta não encontrada' using errcode = 'PT404';
    end if;
    delete from feedback_respostas where resposta_id = p_resposta and estudante_id = p_estudante;
    insert into feedback_respostas (resposta_id, estudante_id, avaliacao, comentario)
    values (p_resposta, p_estudante, p_avaliacao, p_comentario) returning * into v;
    return to_jsonb(v);
end;
$$;

-- -----------------------------------------------------------------------------
-- 4. Validação humana do caso (decisão + justificativa, append-only)
-- -----------------------------------------------------------------------------
-- p: {estudante_id, score_id, atendente_id, decisao, justificativa, categoria_ajustada?,
--     prioridade?, prazo?, status?, assumir_caso}
create or replace function registrar_validacao_caso(p jsonb)
returns jsonb
language plpgsql
as $$
declare
    v_estudante uuid := (p->>'estudante_id')::uuid;
    v_atendente uuid := (p->>'atendente_id')::uuid;
    v_decisao decisao_validacao := (p->>'decisao')::decisao_validacao;
    v_score scores_risco%rowtype;
    v_caso casos_risco%rowtype;
    v_val validacoes_caso%rowtype;
    v_status status_caso;
    v_prioridade prioridade_caso;
    v_prazo date;
    v_resp uuid;
    v_cat categoria_score;
begin
    perform 1 from estudantes where id = v_estudante;
    if not found then
        raise exception 'estudante não encontrado' using errcode = 'PT404';
    end if;

    select * into v_score from scores_risco
     where estudante_id = v_estudante
     order by competencia desc, calculado_em desc limit 1;
    if not found then
        raise exception 'estudante sem score' using errcode = 'PT404';
    end if;
    if v_score.id <> (p->>'score_id')::uuid then
        raise exception 'score mudou' using errcode = 'PT409';
    end if;

    select * into v_caso from casos_risco where estudante_id = v_estudante for update;
    if not found then
        insert into casos_risco (estudante_id, status, prioridade, score_atual_id)
        values (v_estudante, 'novo', coalesce((p->>'prioridade')::prioridade_caso, 'media'), v_score.id)
        returning * into v_caso;
        insert into eventos_caso (caso_id, usuario_id, tipo, de, para, detalhes)
        values (v_caso.id, v_atendente, 'criado', null, 'novo',
                jsonb_build_object('origem', 'validacao', 'categoria_modelo', v_score.categoria));
    end if;

    insert into validacoes_caso (caso_id, score_id, atendente_id, decisao, justificativa, categoria_ajustada,
                                 prioridade_definida, prazo_definido, versao_modelo)
    values (v_caso.id, v_score.id, v_atendente, v_decisao, p->>'justificativa',
            nullif(p->>'categoria_ajustada', '')::categoria_score,
            nullif(p->>'prioridade', '')::prioridade_caso,
            nullif(p->>'prazo', '')::date, v_score.versao_modelo)
    returning * into v_val;

    -- novo estado do caso
    v_status := coalesce(nullif(p->>'status', '')::status_caso,
                         case when v_decisao = 'rejeitado' then 'arquivado'::status_caso
                              when v_caso.status = 'novo' then 'em_acompanhamento'::status_caso
                              else v_caso.status end);
    v_prioridade := coalesce(nullif(p->>'prioridade', '')::prioridade_caso, v_caso.prioridade);
    v_prazo := case when p ? 'prazo' and p->>'prazo' is not null then (p->>'prazo')::date else v_caso.prazo end;
    v_resp := case when coalesce((p->>'assumir_caso')::boolean, true) then v_atendente
                   else v_caso.atendente_responsavel end;
    v_cat := case v_decisao when 'ajustado' then v_val.categoria_ajustada
                            when 'rejeitado' then 'verde'::categoria_score
                            else null end;

    if v_status is distinct from v_caso.status then
        insert into eventos_caso (caso_id, usuario_id, tipo, de, para)
        values (v_caso.id, v_atendente, 'status', v_caso.status::text, v_status::text);
    end if;
    if v_prioridade is distinct from v_caso.prioridade then
        insert into eventos_caso (caso_id, usuario_id, tipo, de, para)
        values (v_caso.id, v_atendente, 'prioridade', v_caso.prioridade::text, v_prioridade::text);
    end if;
    if v_prazo is distinct from v_caso.prazo then
        insert into eventos_caso (caso_id, usuario_id, tipo, de, para)
        values (v_caso.id, v_atendente, 'prazo', v_caso.prazo::text, v_prazo::text);
    end if;
    if v_resp is distinct from v_caso.atendente_responsavel then
        insert into eventos_caso (caso_id, usuario_id, tipo, de, para)
        values (v_caso.id, v_atendente, 'responsavel', v_caso.atendente_responsavel::text, v_resp::text);
    end if;

    update casos_risco
       set status = v_status, prioridade = v_prioridade, prazo = v_prazo,
           atendente_responsavel = v_resp, categoria_vigente = v_cat, score_atual_id = v_score.id
     where id = v_caso.id;

    return to_jsonb(v_val) || jsonb_build_object(
        'atendente_nome', (select nome_completo from perfis where id = v_atendente),
        'caso_status', v_status);
end;
$$;

-- -----------------------------------------------------------------------------
-- 5. Score calculado pelo backend (POST /risco/inferir com persistir=true)
-- -----------------------------------------------------------------------------
-- p: {estudante_id, competencia, probabilidade, score_financeiro, score_academico,
--     score_relacionamento, categoria, fatores, recomendacao, versao_modelo, prioridade_sugerida, usuario_id}
create or replace function registrar_score_risco(p jsonb)
returns uuid
language plpgsql
as $$
declare
    v_id uuid;
    v_caso casos_risco%rowtype;
    v_estudante uuid := (p->>'estudante_id')::uuid;
begin
    insert into scores_risco (estudante_id, competencia, probabilidade, score_financeiro, score_academico,
                              score_relacionamento, categoria, fatores, recomendacao, versao_modelo, calculado_em)
    values (v_estudante, (p->>'competencia')::date, (p->>'probabilidade')::numeric,
            (p->>'score_financeiro')::numeric, (p->>'score_academico')::numeric,
            (p->>'score_relacionamento')::numeric, (p->>'categoria')::categoria_score,
            coalesce(p->'fatores', '[]'::jsonb), p->>'recomendacao', p->>'versao_modelo', now())
    on conflict (estudante_id, competencia, versao_modelo) do update
       set probabilidade = excluded.probabilidade, score_financeiro = excluded.score_financeiro,
           score_academico = excluded.score_academico, score_relacionamento = excluded.score_relacionamento,
           categoria = excluded.categoria, fatores = excluded.fatores, recomendacao = excluded.recomendacao,
           calculado_em = now()
    returning id into v_id;

    select * into v_caso from casos_risco where estudante_id = v_estudante for update;
    if found then
        update casos_risco set score_atual_id = v_id where id = v_caso.id;
    elsif p->>'categoria' in ('amarelo', 'vermelho') then
        -- Abre o caso para o atendente avaliar. Nenhuma ação é executada.
        insert into casos_risco (estudante_id, status, prioridade, score_atual_id)
        values (v_estudante, 'novo', coalesce((p->>'prioridade_sugerida')::prioridade_caso, 'media'), v_id)
        returning * into v_caso;
        insert into eventos_caso (caso_id, usuario_id, tipo, de, para, detalhes)
        values (v_caso.id, nullif(p->>'usuario_id', '')::uuid, 'criado', null, 'novo',
                jsonb_build_object('origem', 'inferencia', 'categoria_modelo', p->>'categoria'));
    end if;
    return v_id;
end;
$$;

-- -----------------------------------------------------------------------------
-- 6. Base de conhecimento
-- -----------------------------------------------------------------------------
-- p: {titulo, categoria, fonte, conteudo, data_atualizacao, usuario_id, chunks:[{conteudo, embedding:[...]}]}
create or replace function publicar_documento(p jsonb)
returns uuid
language plpgsql
as $$
declare
    v_doc uuid;
    v_c jsonb;
    v_ordem int := 0;
    v_data timestamptz := coalesce(nullif(p->>'data_atualizacao', '')::timestamptz, now());
begin
    insert into documentos_oficiais (titulo, categoria, fonte, versao, ativo, data_atualizacao, criado_por)
    values (p->>'titulo', p->>'categoria', p->>'fonte', 1, true, v_data, (p->>'usuario_id')::uuid)
    returning id into v_doc;
    insert into documentos_versoes (documento_id, versao, titulo, categoria, fonte, conteudo, data_atualizacao,
                                    alterado_por, motivo)
    values (v_doc, 1, p->>'titulo', p->>'categoria', p->>'fonte', p->>'conteudo', v_data,
            (p->>'usuario_id')::uuid, 'Cadastro inicial');
    for v_c in select * from jsonb_array_elements(p->'chunks') loop
        v_ordem := v_ordem + 1;
        insert into documentos_chunks (documento_id, ordem, conteudo, embedding, ativo)
        values (v_doc, v_ordem, v_c->>'conteudo', (v_c->>'embedding')::vector, true);
    end loop;
    return v_doc;
end;
$$;

-- p: {documento_id, versao_base, titulo?, categoria?, fonte?, conteudo, motivo, data_atualizacao?, usuario_id, chunks}
create or replace function publicar_nova_versao_documento(p jsonb)
returns int
language plpgsql
as $$
declare
    v_doc documentos_oficiais%rowtype;
    v_nova int;
    v_c jsonb;
    v_ordem int := 0;
    v_data timestamptz := coalesce(nullif(p->>'data_atualizacao', '')::timestamptz, now());
begin
    select * into v_doc from documentos_oficiais where id = (p->>'documento_id')::uuid for update;
    if not found then
        raise exception 'documento não encontrado' using errcode = 'PT404';
    end if;
    if v_doc.versao <> (p->>'versao_base')::int then
        raise exception 'versão mudou' using errcode = 'PT409';
    end if;
    v_nova := v_doc.versao + 1;

    update documentos_oficiais
       set titulo = coalesce(nullif(p->>'titulo', ''), titulo),
           categoria = coalesce(nullif(p->>'categoria', ''), categoria),
           fonte = coalesce(nullif(p->>'fonte', ''), fonte),
           versao = v_nova, data_atualizacao = v_data
     where id = v_doc.id
     returning * into v_doc;

    insert into documentos_versoes (documento_id, versao, titulo, categoria, fonte, conteudo, data_atualizacao,
                                    alterado_por, motivo)
    values (v_doc.id, v_nova, v_doc.titulo, v_doc.categoria, v_doc.fonte, p->>'conteudo', v_data,
            (p->>'usuario_id')::uuid, p->>'motivo');

    -- chunks antigos saem da busca, mas continuam existindo para as evidências antigas
    update documentos_chunks set ativo = false, embedding = null where documento_id = v_doc.id and ativo;
    select coalesce(max(ordem), 0) into v_ordem from documentos_chunks where documento_id = v_doc.id;
    for v_c in select * from jsonb_array_elements(p->'chunks') loop
        v_ordem := v_ordem + 1;
        insert into documentos_chunks (documento_id, ordem, conteudo, embedding, ativo)
        values (v_doc.id, v_ordem, v_c->>'conteudo', (v_c->>'embedding')::vector, true);
    end loop;
    return v_nova;
end;
$$;

create or replace function desativar_documento(p_documento uuid, p_motivo text, p_usuario uuid)
returns void
language plpgsql
as $$
declare
    v_doc documentos_oficiais%rowtype;
begin
    select * into v_doc from documentos_oficiais where id = p_documento for update;
    if not found then
        raise exception 'documento não encontrado' using errcode = 'PT404';
    end if;
    if not v_doc.ativo then
        raise exception 'documento já desativado' using errcode = 'PT409';
    end if;
    update documentos_oficiais
       set ativo = false, desativado_em = now(), desativado_por = p_usuario, motivo_desativacao = p_motivo
     where id = p_documento;
end;
$$;

-- -----------------------------------------------------------------------------
-- 7. Dashboard (só agregados, sem dado individual)
-- -----------------------------------------------------------------------------
create or replace function dashboard_agregados(p_de date, p_ate date)
returns jsonb
language sql stable
as $$
with
ini as (select p_de::timestamptz as de, (p_ate + 1)::timestamptz as ate),
resp as (
    select r.*, c.estudante_id, c.id as conversa_id
      from respostas_agente r
      join mensagens m on m.id = r.mensagem_id
      join conversas c on c.id = m.conversa_id, ini
     where r.criado_em >= ini.de and r.criado_em < ini.ate
),
fb as (
    select f.avaliacao from feedback_respostas f, ini where f.criado_em >= ini.de and f.criado_em < ini.ate
),
dias as (
    select (r.criado_em at time zone 'America/Sao_Paulo')::date as dia,
           count(*) as total, count(*) filter (where r.abstencao) as abstencoes
      from resp r group by 1 order by 1
),
docs as (
    select d.id, d.titulo, count(*) as citacoes
      from resp r
      join resposta_evidencias e on e.resposta_id = r.id and e.posicao_ranking = 1
      join documentos_chunks c on c.id = e.chunk_id
      join documentos_oficiais d on d.id = c.documento_id
     where not r.abstencao
     group by d.id, d.titulo order by citacoes desc limit 10
),
fila as (select categoria, versao_modelo, atualizado_em from vw_fila_risco),
mensal as (
    select competencia,
           count(*) filter (where categoria = 'verde')    as verde,
           count(*) filter (where categoria = 'amarelo')  as amarelo,
           count(*) filter (where categoria = 'vermelho') as vermelho
      from (select distinct on (estudante_id, competencia) estudante_id, competencia, categoria
              from scores_risco order by estudante_id, competencia, calculado_em desc) s
     group by competencia order by competencia desc limit 6
),
val as (
    select v.decisao, extract(epoch from (v.criado_em - s.calculado_em)) / 3600.0 as horas
      from validacoes_caso v left join scores_risco s on s.id = v.score_id, ini
     where v.criado_em >= ini.de and v.criado_em < ini.ate
),
enc as (select e.status from encaminhamentos e, ini where e.criado_em >= ini.de and e.criado_em < ini.ate)
select jsonb_build_object(
    'periodo', jsonb_build_object('de', p_de, 'ate', p_ate),
    'chat', jsonb_build_object(
        'conversas', (select count(distinct conversa_id) from resp),
        'perguntas', (select count(*) from resp),
        'estudantes_ativos', (select count(distinct estudante_id) from resp),
        'taxa_abstencao', coalesce((select round(avg(case when abstencao then 1 else 0 end), 4) from resp), 0),
        'confianca_media', (select round(avg(confianca_score) filter (where not abstencao), 4) from resp),
        'latencia_p95_ms', (select percentile_cont(0.95) within group (order by latencia_ms)::int
                              from resp where latencia_ms is not null),
        'latencia_media_ms', (select avg(latencia_ms)::int from resp where latencia_ms is not null),
        'feedback', jsonb_build_object(
            'util', (select count(*) from fb where avaliacao = 'util'),
            'nao_util', (select count(*) from fb where avaliacao = 'nao_util')),
        'perguntas_por_dia', coalesce((select jsonb_agg(to_jsonb(dias)) from dias), '[]'::jsonb),
        'principais_documentos', coalesce((select jsonb_agg(jsonb_build_object(
            'documento_id', id, 'titulo', titulo, 'citacoes', citacoes)) from docs), '[]'::jsonb)),
    'risco', jsonb_build_object(
        'distribuicao', jsonb_build_object(
            'verde', (select count(*) from fila where categoria = 'verde'),
            'amarelo', (select count(*) from fila where categoria = 'amarelo'),
            'vermelho', (select count(*) from fila where categoria = 'vermelho')),
        'distribuicao_mensal', coalesce((select jsonb_agg(to_jsonb(m) order by m.competencia) from mensal m),
                                        '[]'::jsonb),
        'casos_por_status', coalesce((select jsonb_object_agg(status, n) from
            (select status::text, count(*) as n from casos_risco group by status) s), '{}'::jsonb),
        'versao_modelo', coalesce((select versao_modelo from fila order by atualizado_em desc limit 1), '')),
    'validacoes', jsonb_build_object(
        'confirmado', (select count(*) from val where decisao = 'confirmado'),
        'ajustado', (select count(*) from val where decisao = 'ajustado'),
        'rejeitado', (select count(*) from val where decisao = 'rejeitado'),
        'tempo_medio_ate_validacao_horas', (select round(avg(horas)::numeric, 1) from val where horas >= 0)),
    'encaminhamentos', jsonb_build_object(
        'abertos', (select count(*) from enc where status = 'aberto'),
        'em_andamento', (select count(*) from enc where status = 'em_andamento'),
        'resolvidos', (select count(*) from enc where status = 'resolvido')),
    'atualizado_em', now()
);
$$;

-- -----------------------------------------------------------------------------
-- 8. Só o backend (service_role) executa as RPCs
-- -----------------------------------------------------------------------------
do $$
declare
    f text;
begin
    foreach f in array array[
        'registrar_resposta_chat(jsonb)',
        'salvar_feedback(uuid, uuid, text, text)',
        'registrar_validacao_caso(jsonb)',
        'registrar_score_risco(jsonb)',
        'publicar_documento(jsonb)',
        'publicar_nova_versao_documento(jsonb)',
        'desativar_documento(uuid, text, uuid)',
        'dashboard_agregados(date, date)'
    ] loop
        execute format('revoke all on function %s from public', f);
        if exists (select 1 from pg_roles where rolname = 'anon') then
            execute format('revoke all on function %s from anon, authenticated', f);
        end if;
        if exists (select 1 from pg_roles where rolname = 'service_role') then
            execute format('grant execute on function %s to service_role', f);
        end if;
    end loop;
end $$;

commit;
