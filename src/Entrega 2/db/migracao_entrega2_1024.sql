-- =============================================================================
-- MIGRAÇÃO Entrega 2 - embeddings de 384 -> 1024 dimensões
-- =============================================================================
-- Por que: a Entrega 1 usava BAAI/bge-small-en-v1.5 (384 dimensões) via Hugging
-- Face. Dois problemas apareceram:
--
--   1. O token da Hugging Face ficou sem créditos (HTTP 402) e a vetorização
--      parou de funcionar em produção.
--   2. bge-small-en-v1.5 é um modelo treinado em INGLÊS, e toda a base de
--      conhecimento está em português. Isso explica a similaridade "de base"
--      alta (~0.60-0.66) que aparecia até para perguntas totalmente fora de
--      escopo, e que obrigou a subir o CONFIDENCE_THRESHOLD às cegas.
--
-- A Entrega 2 passa a usar @cf/baai/bge-m3 (Cloudflare Workers AI), que é
-- multilíngue de verdade e tem 1024 dimensões - daí esta migração.
--
-- Rode no SQL Editor do Supabase ANTES de rodar o gerar_embeddings.py.
-- =============================================================================

begin;

-- ---------------------------------------------------------------------------
-- 1. Remove o índice vetorial antigo
-- ---------------------------------------------------------------------------
-- Além de estar preso a 384 dimensões, esse índice estava mal dimensionado:
-- ivfflat com lists = 100 sobre 693 linhas dá ~7 linhas por lista. Com o
-- padrão ivfflat.probes = 1, a busca varria ~7 linhas da base inteira, ou
-- seja, o índice estava PIORANDO o recall em vez de acelerar nada relevante.
drop index if exists documentos_chunks_embedding_idx;

-- O nome acima é o gerado automaticamente por "create index on ... using
-- ivfflat". Se no seu banco ele tiver outro nome, descubra com:
--   select indexname from pg_indexes where tablename = 'documentos_chunks';

-- ---------------------------------------------------------------------------
-- 2. Troca a dimensão da coluna
-- ---------------------------------------------------------------------------
-- Os vetores antigos não servem para o modelo novo, então zera tudo primeiro.
-- O gerar_embeddings.py repreenche logo em seguida.
update documentos_chunks set embedding = null;

alter table documentos_chunks
    alter column embedding type vector(1024);

comment on column documentos_chunks.embedding is
    'Embedding de 1024 dimensões, normalizado (norma L2 = 1). Modelo: @cf/baai/bge-m3 via Cloudflare Workers AI. Gerado por src/Entrega 2/gerar_embeddings.py.';

-- ---------------------------------------------------------------------------
-- 3. Recria a função de busca com a nova dimensão
-- ---------------------------------------------------------------------------
-- Precisa de drop explícito: mudar o tipo de um parâmetro cria uma sobrecarga
-- nova em vez de substituir a função, e aí a API passa a receber o erro
-- "could not choose a best candidate function".
drop function if exists buscar_chunks_similares(vector(384), int, float);
drop function if exists buscar_chunks_similares(vector(1024), int, float);

create function buscar_chunks_similares(
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
      and dc.embedding is not null
      and 1 - (dc.embedding <=> query_embedding) >= limiar_similaridade
    order by dc.embedding <=> query_embedding
    limit limite;
$$;

-- ---------------------------------------------------------------------------
-- 4. Índice novo (HNSW)
-- ---------------------------------------------------------------------------
-- HNSW no lugar de ivfflat: não exige escolher "lists" em função do tamanho da
-- base (foi exatamente isso que quebrou o índice anterior) e mantém recall alto
-- tanto nas 693 linhas de hoje quanto se a base crescer.
create index documentos_chunks_embedding_idx
    on documentos_chunks using hnsw (embedding vector_cosine_ops);

commit;

-- =============================================================================
-- Conferência
-- =============================================================================
--   select atttypmod from pg_attribute
--    where attrelid = 'documentos_chunks'::regclass and attname = 'embedding';
--   -- esperado: 1024
--
--   select count(*) from documentos_chunks where embedding is not null;
--   -- esperado: 0 agora, 693 depois do gerar_embeddings.py
