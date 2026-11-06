-- =============================================================================
-- 004 · Textos exibidos ao usuário (sem termos técnicos). IDEMPOTENTE.
-- A 002 registrou a versão vigente de cada documento com o motivo
-- "Versão inicial (migração 002)", que aparece na tela de versões do admin.
-- =============================================================================
update documentos_versoes
   set motivo = 'Versão importada da base oficial'
 where motivo = 'Versão inicial (migração 002)';
