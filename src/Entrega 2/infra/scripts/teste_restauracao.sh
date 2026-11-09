#!/usr/bin/env bash
# =============================================================================
# ASA Turbo · TESTE DE RESTAURAÇÃO num Postgres LIMPO (não toca a produção)
#
#   infra/scripts/teste_restauracao.sh                       # último backup de BACKUP_DIR
#   infra/scripts/teste_restauracao.sh backups/asa_<ts>.dump
#
# 1. Sobe um projeto compose SEPARADO ("asa-restore": volume novo, rede própria,
#    sem portas) só com db (supabase/postgres 15 + pgvector) e GoTrue, que cria o
#    schema auth vazio. Nenhuma migration nem seed roda.
# 2. Confere o sha256, cria as extensões, carrega auth (asa_<ts>_auth.sql.gz) e
#    restaura o schema public (pg_restore em transação única).
# 3. Compara as contagens por tabela com asa_<ts>.contagens (gravado no backup).
# 4. Mede o tempo de cada etapa, imprime o relatório e derruba o projeto de teste.
# Saída (stdout) pronta para virar evidência.
# =============================================================================
set -euo pipefail
# shellcheck source=infra/scripts/_comum.sh
source "$(dirname "${BASH_SOURCE[0]}")/_comum.sh"

dir="$(ler_env BACKUP_DIR "$RAIZ/backups")"
case "$dir" in /*) ;; *) dir="$RAIZ/${dir#./}" ;; esac
dump="${1:-$(ls -1t "$dir"/asa_*.dump 2>/dev/null | head -n1)}"
[ -f "$dump" ] || { log "nenhum dump encontrado em $dir"; exit 2; }
base="${dump%.dump}"; ts="${base##*/asa_}"
PROJ=asa-restore
DC=(docker compose -p "$PROJ" --project-directory "$RAIZ" --profile local)
agora() { date +%s.%N; }
dur() { awk -v a="$1" -v b="$2" 'BEGIN{printf "%.1f", b-a}'; }
psql_t() { "${DC[@]}" exec -T -e PGOPTIONS="-c client_min_messages=warning" -e PGPASSWORD="$(ler_env POSTGRES_PASSWORD)" db psql -X -v ON_ERROR_STOP=1 -q -h localhost -U supabase_admin -d postgres "$@"; }

limpar() { "${DC[@]}" down -v --remove-orphans >/dev/null 2>&1 || true; }
trap limpar EXIT

echo "# Teste de restauração · ASA Turbo · $(date '+%Y-%m-%d %H:%M:%S %Z') · host $(hostname)"
echo "# backup: $(basename "$dump") ($(du -h "$dump" | cut -f1)) · destino: projeto compose '$PROJ' (Postgres limpo)"
t0=$(agora)

# --- 0. integridade
if [ -f "$base.sha256" ]; then
  (cd "$(dirname "$dump")" && sha256sum -c "$(basename "$base.sha256")") | sed 's/^/  sha256 /'
else
  echo "  aviso: sem $base.sha256"
fi

# --- 1. Postgres limpo
limpar
t1=$(agora)
"${DC[@]}" up -d --wait db gotrue >/dev/null 2>&1
until psql_t -tAc "select 1 from information_schema.columns where table_schema='auth' and table_name='identities' and column_name='provider_id'" 2>/dev/null | grep -q 1; do sleep 1; done
t2=$(agora)
echo "1. Postgres limpo no ar (db + GoTrue, schema auth vazio): $(dur "$t1" "$t2") s"
echo "   tabelas em public antes: $(psql_t -tAc "select count(*) from pg_tables where schemaname='public'")"

# --- 2. extensões + auth + public
psql_t -c 'create extension if not exists "uuid-ossp" with schema extensions; create extension if not exists vector with schema extensions; create extension if not exists pg_trgm with schema extensions; create extension if not exists unaccent with schema extensions; create extension if not exists pgcrypto with schema extensions;'
if [ -f "${base}_auth.sql.gz" ]; then
  gunzip -c "${base}_auth.sql.gz" | psql_t >/dev/null
  echo "   auth.users restaurados: $(psql_t -tAc 'select count(*) from auth.users')"
fi
t3=$(agora)
lista="$(mktemp)"; trap 'rm -f "$lista"; limpar' EXIT
filtro="$(printf '%s\n' $TABELAS_FORA_DO_BACKUP | paste -sd'|' -)"
docker run --rm -i "$IMAGEM_PG_CLIENTE" pg_restore --list < "$dump" \
  | grep -Ev " (${filtro})( |$)" | grep -Ev "SCHEMA - public |- SCHEMA public |DEFAULT ACL " > "$lista"
chmod 644 "$lista"
"${DC[@]}" cp "$lista" db:/tmp/asa_restore.list >/dev/null 2>&1
"${DC[@]}" exec -T -e PGPASSWORD="$(ler_env POSTGRES_PASSWORD)" db \
  pg_restore -h localhost -U postgres -d postgres --no-owner --single-transaction --exit-on-error \
  --use-list=/tmp/asa_restore.list < "$dump"
t4=$(agora)
echo "2. restauração (auth + public): $(dur "$t2" "$t4") s (pg_restore do public: $(dur "$t3" "$t4") s)"

# --- 3. conferência
echo "3. contagem de linhas: backup x restaurado"
printf '   %-22s %10s %12s  %s\n' tabela backup restaurado ok
divergencias=0
declare -A esperado=()
if [ -f "$base.contagens" ]; then
  while IFS='|' read -r t n; do esperado[$t]=$n; done < "$base.contagens"
fi
for t in $TABELAS_CONFERENCIA; do
  n="$(psql_t -tAc "select count(*) from public.$t")"
  e="${esperado[$t]:-?}"
  marca=sim; [ "$e" != "$n" ] && { marca=NAO; divergencias=$((divergencias + 1)); }
  printf '   %-22s %10s %12s  %s\n' "$t" "$e" "$n" "$marca"
done
echo "   checagens extras: $(psql_t -tAc "select count(*) from public.documentos_chunks where embedding is not null") chunks com embedding (pgvector) · $(psql_t -tAc "select count(*) from pg_policies where schemaname='public'") policies RLS"
t5=$(agora)
echo
echo "RESULTADO: $([ "$divergencias" = 0 ] && echo "OK, todas as tabelas conferem" || echo "$divergencias tabela(s) divergente(s)")"
echo "TEMPO TOTAL (Postgres limpo -> dados conferidos): $(dur "$t0" "$t5") s"
exit "$divergencias"
