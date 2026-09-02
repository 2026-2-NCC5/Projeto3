-- =============================================================================
-- SEED - Dados fictícios para demonstração (nenhum dado real, conforme o edital)
-- Rode DEPOIS do schema.sql
-- =============================================================================

-- Documentos oficiais (base de conhecimento)
insert into documentos_oficiais (id, titulo, categoria, fonte, versao, data_atualizacao) values
('11111111-1111-1111-1111-111111111111', 'Manual do Aluno - Rematrícula', 'manual_aluno', 'Manual do Aluno - Seção 4.2', 1, '2026-08-12'),
('22222222-2222-2222-2222-222222222222', 'Central de Documentos', 'procedimento', 'Portal do Aluno - Central de Documentos', 1, '2026-07-03'),
('33333333-3333-3333-3333-333333333333', 'Regulamento - Trancamento', 'regulamento', 'Regulamento Acadêmico - Art. 27', 1, '2026-02-20'),
('44444444-4444-4444-4444-444444444444', 'Manual do Aluno - Financiamentos', 'financeiro', 'Manual do Aluno - Seção 6.1', 1, '2026-01-15'),
('55555555-5555-5555-5555-555555555555', 'Regulamento - Frequência', 'regulamento', 'Regulamento Acadêmico - Art. 14', 1, '2026-03-08');

-- Chunks de texto (SEM embedding preenchido — o embedding real deve ser gerado
-- pelo backend/notebook de vocês com o modelo escolhido, ex: sentence-transformers)
insert into documentos_chunks (documento_id, ordem, conteudo) values
('11111111-1111-1111-1111-111111111111', 1, 'A rematrícula exige ausência de pendências financeiras e envio do comprovante de endereço atualizado. O prazo se encerra 10 dias antes do início do semestre letivo.'),
('22222222-2222-2222-2222-222222222222', 1, 'A declaração de matrícula pode ser emitida na aba Documentos, opção Declarações, em formato PDF, com validade de 90 dias, sem custo.'),
('33333333-3333-3333-3333-333333333333', 1, 'O trancamento de matrícula deve ser solicitado com 15 dias de antecedência do início do semestre e pode impactar bolsas ou financiamentos ativos.'),
('44444444-4444-4444-4444-444444444444', 1, 'Bolsas e financiamentos precisam ser renovados a cada semestre. A renovação abre 30 dias antes do início do período letivo, direto pelo portal financeiro.'),
('55555555-5555-5555-5555-555555555555', 1, 'O estudante que ultrapassar 25% de faltas em qualquer disciplina fica automaticamente reprovado por frequência, independente da nota obtida.');

-- Nota: os perfis (perfis/estudantes) dependem de usuários criados via
-- Supabase Auth (auth.users). Crie primeiro os usuários de teste em
-- Authentication > Users no painel do Supabase, copie o UUID gerado,
-- e use esse UUID nos inserts abaixo (substitua os placeholders).

-- Exemplo (ajuste o UUID pelo real gerado no Supabase Auth):
-- insert into perfis (id, papel, nome_completo, email) values
-- ('SUBSTITUA-PELO-UUID-DO-AUTH', 'estudante', 'João Silva', 'joao.silva@aluno.fecap.br');

-- insert into estudantes (id, ra, curso, semestre_atual, status) values
-- ('SUBSTITUA-PELO-UUID-DO-AUTH', '20260001', 'Ciência da Computação', 5, 'regular');

-- insert into situacao_financeira (estudante_id, adimplente, quantidade_pendencias) values
-- ('SUBSTITUA-PELO-UUID-DO-AUTH', true, 0);

-- insert into situacao_academica (estudante_id, media_geral, percentual_frequencia, quantidade_reprovacoes, tendencia_desempenho) values
-- ('SUBSTITUA-PELO-UUID-DO-AUTH', 8.20, 92.5, 0, 'estavel');
