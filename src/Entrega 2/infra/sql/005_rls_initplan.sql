-- =============================================================================
-- 005 · Desempenho das policies RLS (achado do teste de estresse, 09/11/2026)
--
-- Problema: as policies chamam eh_equipe_asa(), eh_admin(), meu_estudante_id() e
-- uid() direto no USING/WITH CHECK. O Postgres reavalia a função PARA CADA LINHA.
-- Como as views da fila são security_invoker, "count(*) from vw_fila_risco_busca"
-- de um atendente levava ~350 ms (2,7 ms sem RLS) e o GET /casos faz 4 dessas
-- consultas: o Postgres virou o maior consumidor de CPU da VM.
--
-- Correção (recomendada pelo Supabase): envolver a chamada em (select ...). Vira um
-- InitPlan, avaliado UMA vez por consulta. A semântica não muda: as funções são
-- STABLE e não dependem da linha.
-- Idempotente: só reescreve o que ainda não está envolvido.
-- =============================================================================
begin;

do $$
declare
  p record;
  -- função sem argumentos, não precedida de "." nem de letra (não pega auth.uid())
  padrao constant text := '(?<![.\w])(eh_equipe_asa|eh_admin|meu_estudante_id|uid)\(\)';
  novo_using text;
  novo_check text;
  cmd text;
  alteradas int := 0;
begin
  for p in
    select schemaname, tablename, policyname, qual, with_check
      from pg_policies
     where schemaname = 'public'
       -- conforme o search_path de quem roda, o Postgres mostra uid() ou auth.uid()
       and (replace(coalesce(qual, ''), 'auth.uid()', 'uid()') ~ padrao
            or replace(coalesce(with_check, ''), 'auth.uid()', 'uid()') ~ padrao)
       -- já reescrita (o Postgres mostra "( SELECT eh_equipe_asa() AS eh_equipe_asa)")
       and coalesce(qual, '') || coalesce(with_check, '')
           !~* 'select\s+((public|auth)\.)?(eh_equipe_asa|eh_admin|meu_estudante_id|uid)\(\)'
       -- (uma policy só com auth.uid() ainda não envolvida continua elegível)
  loop
    novo_using := regexp_replace(replace(p.qual, 'auth.uid()', 'uid()'), padrao, '(select \1())', 'g');
    novo_check := regexp_replace(replace(p.with_check, 'auth.uid()', 'uid()'), padrao, '(select \1())', 'g');
    -- uid() resolve para auth.uid(); as demais vivem em public
    novo_using := replace(novo_using, '(select uid())', '(select auth.uid())');
    novo_check := replace(novo_check, '(select uid())', '(select auth.uid())');
    novo_using := regexp_replace(novo_using, '\(select (eh_equipe_asa|eh_admin|meu_estudante_id)\(\)\)', '(select public.\1())', 'g');
    novo_check := regexp_replace(novo_check, '\(select (eh_equipe_asa|eh_admin|meu_estudante_id)\(\)\)', '(select public.\1())', 'g');
    cmd := format('alter policy %I on %I.%I', p.policyname, p.schemaname, p.tablename);
    if novo_using is not null then cmd := cmd || format(' using (%s)', novo_using); end if;
    if novo_check is not null then cmd := cmd || format(' with check (%s)', novo_check); end if;
    execute cmd;
    alteradas := alteradas + 1;
  end loop;
  raise notice '005_rls_initplan: % policies reescritas', alteradas;
end
$$;

commit;
