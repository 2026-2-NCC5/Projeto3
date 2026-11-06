#!/bin/sh
# =============================================================================
# Inicializa o banco LOCAL (job do compose, profile "local"). Idempotente.
#   1. migrations infra/sql/001..00N (registradas em public._asa_migracoes)
#   2. base de conhecimento oficial (só se vazia)
#   3. usuários de demonstração em auth.users/auth.identities + perfis
#   4. seed_demo.sql (só se ainda não houver estudantes de demo)
# Requer: PGHOST, PGPASSWORD (senha comum aos papéis locais), DEMO_PASSWORD.
# =============================================================================
set -eu
export PGHOST="${PGHOST:-db}" PGDATABASE=postgres
PSQL="psql -v ON_ERROR_STOP=1 -q -X"
ADMIN="$PSQL -U supabase_admin"   # superusuário local (cria extensões e mexe em auth.*)
APP="$PSQL -U postgres"           # mesmo papel que roda o SQL Editor no Supabase real

echo "[init-db] aguardando o GoTrue criar o schema auth..."
i=0
until $ADMIN -tAc "select 1 from information_schema.columns where table_schema='auth' and table_name='identities' and column_name='provider_id'" | grep -q 1; do
  i=$((i+1)); [ $i -gt 60 ] && { echo "[init-db] GoTrue não migrou o schema auth"; exit 1; }
  sleep 2
done

$ADMIN -c "create table if not exists public._asa_migracoes (arquivo text primary key, aplicado_em timestamptz default now())"
$ADMIN -c "grant select on public._asa_migracoes to postgres"

aplicar() {  # aplicar <arquivo> <psql>
  nome=$(basename "$1")
  if [ -n "$($ADMIN -tAc "select 1 from public._asa_migracoes where arquivo='$nome'")" ]; then
    echo "[init-db] $nome já aplicado"; return 0
  fi
  echo "[init-db] aplicando $nome"
  $2 -f "$1"
  $ADMIN -c "insert into public._asa_migracoes(arquivo) values ('$nome')"
}

# Extensões exigem superusuário fora do Supabase gerenciado
$ADMIN -c 'create extension if not exists "uuid-ossp" with schema extensions; create extension if not exists vector with schema extensions; create extension if not exists pg_trgm with schema extensions; create extension if not exists unaccent with schema extensions;'

aplicar /sql/001_schema_base.sql "$APP"
if [ "$($ADMIN -tAc 'select count(*) from documentos_oficiais')" = "0" ]; then
  echo "[init-db] carregando a base de conhecimento oficial"
  $APP -f /seeds/base_conhecimento_oficial.sql
fi
for f in /sql/0*.sql; do
  case "$(basename "$f")" in 001_*) continue ;; esac
  aplicar "$f" "$APP"
done

echo "[init-db] usuários de demonstração"
$ADMIN -v senha="$DEMO_PASSWORD" <<'SQL'
create extension if not exists pgcrypto with schema extensions;
with u(id, email, papel, nome) as (values
  ('d0000000-0000-4000-8000-000000000001'::uuid, 'estudante.demo@example.com', 'estudante', 'Júlia Prado (demo)'),
  ('d0000000-0000-4000-8000-000000000002'::uuid, 'atendente.demo@example.com', 'atendente', 'Marcos Lima (demo)'),
  ('d0000000-0000-4000-8000-000000000003'::uuid, 'admin.demo@example.com', 'administrador', 'Renata Alves (demo)')
)
insert into auth.users (instance_id, id, aud, role, email, encrypted_password, email_confirmed_at,
                        raw_app_meta_data, raw_user_meta_data, created_at, updated_at,
                        confirmation_token, recovery_token, email_change_token_new, email_change)
select '00000000-0000-0000-0000-000000000000', id, 'authenticated', 'authenticated', email,
       extensions.crypt(:'senha', extensions.gen_salt('bf')), now(),
       '{"provider":"email","providers":["email"]}', jsonb_build_object('nome', nome, 'demo', true),
       now(), now(), '', '', '', ''
  from u
on conflict (id) do update set encrypted_password = excluded.encrypted_password;

insert into auth.identities (id, user_id, provider_id, identity_data, provider, last_sign_in_at, created_at, updated_at)
select gen_random_uuid(), u.id, u.id::text, jsonb_build_object('sub', u.id::text, 'email', u.email), 'email', now(), now(), now()
  from auth.users u
 where u.email like '%.demo@example.com'
   and not exists (select 1 from auth.identities i where i.user_id = u.id and i.provider = 'email');

insert into public.perfis (id, papel, nome_completo, email) values
  ('d0000000-0000-4000-8000-000000000001', 'estudante', 'Júlia Prado (demo)', 'estudante.demo@example.com'),
  ('d0000000-0000-4000-8000-000000000002', 'atendente', 'Marcos Lima (demo)', 'atendente.demo@example.com'),
  ('d0000000-0000-4000-8000-000000000003', 'administrador', 'Renata Alves (demo)', 'admin.demo@example.com')
on conflict (id) do update set papel = excluded.papel, nome_completo = excluded.nome_completo, ativo = true;
SQL

if [ "$($ADMIN -tAc "select count(*) from estudantes where ra like '99%'")" = "0" ]; then
  echo "[init-db] carregando seed_demo.sql"
  $APP -f /seeds/seed_demo.sql
fi

# PostgREST relê o schema (views/RPCs novas)
$ADMIN -c "notify pgrst, 'reload schema'"
echo "[init-db] pronto"
