#!/bin/sh
# Cria usuários FICTÍCIOS para o teste em rampa (rampa.js), no Postgres do compose
# (profile "local", na máquina local ou na VM). Idempotente. Nunca use em banco com dados reais.
#   sh infra/loadtest/criar_usuarios_rampa.sh            # 100 estudantes + 10 atendentes
#   N_EST=120 N_ATD=12 sh infra/loadtest/criar_usuarios_rampa.sh
# E-mails: carga.e001@example.com ... e carga.a01@example.com ... (senha = DEMO_PASSWORD)
set -eu
cd "$(dirname "$0")/../.."
SENHA="$(grep -E '^DEMO_PASSWORD=' .env | tail -n1 | cut -d= -f2- | sed "s/^['\"]//; s/['\"]$//")"
N_EST="${N_EST:-100}"; N_ATD="${N_ATD:-10}"
docker compose exec -T db psql -v ON_ERROR_STOP=1 -q -U supabase_admin -d postgres \
  -v senha="$SENHA" -v nest="$N_EST" -v natd="$N_ATD" <<'SQL'
with u as (
  select format('c1000000-0000-4000-8000-%s', lpad(n::text, 12, '0'))::uuid as id,
         case when n <= :nest then format('carga.e%s@example.com', lpad(n::text, 3, '0'))
              else format('carga.a%s@example.com', lpad((n - :nest)::text, 2, '0')) end as email
    from generate_series(1, :nest + :natd) n
)
insert into auth.users (instance_id, id, aud, role, email, encrypted_password, email_confirmed_at,
                        raw_app_meta_data, raw_user_meta_data, created_at, updated_at,
                        confirmation_token, recovery_token, email_change_token_new, email_change)
select '00000000-0000-0000-0000-000000000000', id, 'authenticated', 'authenticated', email,
       extensions.crypt(:'senha', extensions.gen_salt('bf')), now(),
       '{"provider":"email","providers":["email"]}', '{"carga":true}', now(), now(), '', '', '', ''
  from u
on conflict (id) do update set encrypted_password = excluded.encrypted_password;

insert into auth.identities (id, user_id, provider_id, identity_data, provider, created_at, updated_at)
select gen_random_uuid(), u.id, u.id::text, jsonb_build_object('sub', u.id::text, 'email', u.email), 'email', now(), now()
  from auth.users u
 where u.email ~ '^carga\.[ea][0-9]+@example\.com$'
   and not exists (select 1 from auth.identities i where i.user_id = u.id);

insert into public.perfis (id, papel, nome_completo, email)
select id, (case when email like 'carga.e%' then 'estudante' else 'atendente' end)::papel_usuario,
       'Carga ' || split_part(email, '@', 1), email
  from auth.users where email ~ '^carga\.[ea][0-9]+@example\.com$'
on conflict (id) do nothing;

insert into public.estudantes (id, perfil_id, ra, nome_exibicao, curso, semestre_atual, status)
select p.id, p.id, '97' || lpad(substring(p.email from 'carga\.e([0-9]+)@'), 6, '0'), p.nome_completo, 'Administração', 2, 'regular'
  from public.perfis p
 where p.email ~ '^carga\.e[0-9]+@example\.com$'
   and not exists (select 1 from public.estudantes e where e.perfil_id = p.id);

select count(*) filter (where email like 'carga.e%') as estudantes,
       count(*) filter (where email like 'carga.a%') as atendentes
  from auth.users where email ~ '^carga\.[ea][0-9]+@example\.com$';
SQL
