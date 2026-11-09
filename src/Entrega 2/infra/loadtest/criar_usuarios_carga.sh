#!/bin/sh
# Cria 50 estudantes + 5 atendentes FICTÍCIOS só para o teste de carga, na stack LOCAL
# (docker compose, profile "local"). Nunca rode contra produção.
#   sh infra/loadtest/criar_usuarios_carga.sh
set -eu
cd "$(dirname "$0")/../.."
. ./.env
docker compose exec -T db psql -v ON_ERROR_STOP=1 -q -U supabase_admin -d postgres -v senha="$DEMO_PASSWORD" <<'SQL'
with u as (
  select format('c0000000-0000-4000-8000-%s', lpad(n::text, 12, '0'))::uuid as id,
         case when n <= 50 then format('carga.estudante%s@example.com', lpad(n::text, 2, '0'))
              else format('carga.atendente%s@example.com', lpad((n-50)::text, 2, '0')) end as email,
         case when n <= 50 then 'estudante' else 'atendente' end as papel, n
    from generate_series(1, 55) n
), ins as (
  insert into auth.users (instance_id, id, aud, role, email, encrypted_password, email_confirmed_at,
                          raw_app_meta_data, raw_user_meta_data, created_at, updated_at,
                          confirmation_token, recovery_token, email_change_token_new, email_change)
  select '00000000-0000-0000-0000-000000000000', id, 'authenticated', 'authenticated', email,
         extensions.crypt(:'senha', extensions.gen_salt('bf')), now(),
         '{"provider":"email","providers":["email"]}', '{"carga":true}', now(), now(), '', '', '', ''
    from u
  on conflict (id) do nothing
  returning id
)
select count(*) from ins;

insert into auth.identities (id, user_id, provider_id, identity_data, provider, created_at, updated_at)
select gen_random_uuid(), u.id, u.id::text, jsonb_build_object('sub', u.id::text, 'email', u.email), 'email', now(), now()
  from auth.users u
 where u.email like 'carga.%@example.com'
   and not exists (select 1 from auth.identities i where i.user_id = u.id);

insert into public.perfis (id, papel, nome_completo, email)
select id, (case when email like 'carga.estudante%' then 'estudante' else 'atendente' end)::papel_usuario,
       'Carga ' || split_part(email, '@', 1), email
  from auth.users where email like 'carga.%@example.com'
on conflict (id) do nothing;

insert into public.estudantes (id, perfil_id, ra, nome_exibicao, curso, semestre_atual, status)
select p.id, p.id, '98' || lpad(row_number() over (order by p.email)::text, 6, '0'), p.nome_completo, 'Administração', 2, 'regular'
  from public.perfis p
 where p.email like 'carga.estudante%' and not exists (select 1 from public.estudantes e where e.perfil_id = p.id);
SQL
echo "usuários de carga prontos"
