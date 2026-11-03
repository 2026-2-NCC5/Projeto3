-- Executado UMA vez pelo init do supabase/postgres (banco novo).
-- Define a senha dos papéis internos usados pelo PostgREST e pelo GoTrue locais.
\set pgpass `echo "$POSTGRES_PASSWORD"`

ALTER USER authenticator WITH PASSWORD :'pgpass';
ALTER USER supabase_auth_admin WITH PASSWORD :'pgpass';
ALTER USER postgres WITH PASSWORD :'pgpass';
