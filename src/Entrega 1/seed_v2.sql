-- =============================================================================
-- SEED v2 - Base de conhecimento ampliada (dados fictícios)
-- Rode isso no SQL Editor do Supabase. Pode rodar por cima do seed antigo:
-- primeiro apaga os dados antigos, depois insere o conjunto novo e maior.
-- =============================================================================

delete from documentos_chunks;
delete from documentos_oficiais;

insert into documentos_oficiais (id, titulo, categoria, fonte, versao, data_atualizacao) values
('11111111-1111-1111-1111-111111111111', 'Rematrícula', 'manual_aluno', 'Manual do Aluno - Seção 4.2', 1, '2026-08-12'),
('22222222-2222-2222-2222-222222222222', 'Declaração de Matrícula', 'procedimento', 'Portal do Aluno - Central de Documentos', 1, '2026-07-03'),
('33333333-3333-3333-3333-333333333333', 'Trancamento de Matrícula', 'regulamento', 'Regulamento Acadêmico - Art. 27', 1, '2026-02-20'),
('44444444-4444-4444-4444-444444444444', 'Bolsas e Financiamentos', 'financeiro', 'Manual do Aluno - Seção 6.1', 1, '2026-01-15'),
('55555555-5555-5555-5555-555555555555', 'Reprovação por Frequência', 'regulamento', 'Regulamento Acadêmico - Art. 14', 1, '2026-03-08'),
('66666666-6666-6666-6666-666666666666', 'Calendário Acadêmico', 'manual_aluno', 'Manual do Aluno - Seção 5.4', 1, '2026-01-02'),
('77777777-7777-7777-7777-777777777777', 'Segunda Chamada de Prova', 'procedimento', 'Regulamento Acadêmico - Art. 18', 1, '2026-02-10'),
('88888888-8888-8888-8888-888888888888', 'Revisão de Nota / Recurso', 'procedimento', 'Regulamento Acadêmico - Art. 19', 1, '2026-02-10'),
('99999999-9999-9999-9999-999999999999', 'Aproveitamento de Disciplinas', 'procedimento', 'Manual do Aluno - Seção 3.7', 1, '2026-04-01'),
('a0000000-0000-0000-0000-000000000001', 'Transferência de Curso ou Turno', 'procedimento', 'Manual do Aluno - Seção 3.9', 1, '2026-04-01'),
('a0000000-0000-0000-0000-000000000002', 'Cancelamento de Matrícula', 'regulamento', 'Regulamento Acadêmico - Art. 29', 1, '2026-02-20'),
('a0000000-0000-0000-0000-000000000003', 'Estágio Obrigatório', 'procedimento', 'Manual do Aluno - Seção 7.1', 1, '2026-05-10'),
('a0000000-0000-0000-0000-000000000004', 'Trabalho de Conclusão de Curso (TCC)', 'procedimento', 'Manual do Aluno - Seção 7.3', 1, '2026-05-10'),
('a0000000-0000-0000-0000-000000000005', 'Biblioteca - Empréstimo de Livros', 'procedimento', 'Manual do Aluno - Seção 8.1', 1, '2026-03-01'),
('a0000000-0000-0000-0000-000000000006', 'Carreira e Empregabilidade (ASA)', 'procedimento', 'Portal ASA - Carreira', 1, '2026-06-01'),
('a0000000-0000-0000-0000-000000000007', 'Atestado Médico e Justificativa de Falta', 'regulamento', 'Regulamento Acadêmico - Art. 16', 1, '2026-02-15'),
('a0000000-0000-0000-0000-000000000008', 'Mudança de Turno', 'procedimento', 'Manual do Aluno - Seção 3.8', 1, '2026-04-01'),
('a0000000-0000-0000-0000-000000000009', 'Certificado e Diploma', 'procedimento', 'Manual do Aluno - Seção 9.1', 1, '2026-06-15'),
('a0000000-0000-0000-0000-000000000010', 'Programa de Intercâmbio', 'procedimento', 'Portal ASA - Internacional', 1, '2026-05-20'),
('a0000000-0000-0000-0000-000000000011', 'Auxílio Financeiro Emergencial', 'financeiro', 'Manual do Aluno - Seção 6.4', 1, '2026-03-20');

insert into documentos_chunks (documento_id, ordem, conteudo) values
('11111111-1111-1111-1111-111111111111', 1, 'A rematrícula exige ausência de pendências financeiras e envio do comprovante de endereço atualizado. O prazo se encerra 10 dias antes do início do semestre letivo.'),

('22222222-2222-2222-2222-222222222222', 1, 'A declaração de matrícula pode ser emitida na aba Documentos, opção Declarações, em formato PDF, com validade de 90 dias, sem custo.'),

('33333333-3333-3333-3333-333333333333', 1, 'O trancamento de matrícula deve ser solicitado com 15 dias de antecedência do início do semestre e pode impactar bolsas ou financiamentos ativos.'),

('44444444-4444-4444-4444-444444444444', 1, 'Bolsas e financiamentos, incluindo FIES e PROUNI, precisam ser renovados a cada semestre. A renovação abre 30 dias antes do início do período letivo, direto pelo portal financeiro.'),

('55555555-5555-5555-5555-555555555555', 1, 'O estudante que ultrapassar 25% de faltas em qualquer disciplina fica automaticamente reprovado por frequência, independente da nota obtida.'),

('66666666-6666-6666-6666-666666666666', 1, 'O calendário acadêmico completo, com datas de provas, feriados e período de rematrícula, fica disponível na aba Boletim do portal e também no aplicativo institucional.'),

('77777777-7777-7777-7777-777777777777', 1, 'A segunda chamada de prova pode ser solicitada em até 3 dias úteis após a data original da avaliação, mediante justificativa e comprovante (atestado médico, atestado de óbito ou declaração de trabalho).'),

('88888888-8888-8888-8888-888888888888', 1, 'O pedido de revisão de nota deve ser feito em até 5 dias úteis após a divulgação do resultado, diretamente com o professor responsável pela disciplina, através do portal acadêmico.'),

('99999999-9999-9999-9999-999999999999', 1, 'O aproveitamento de disciplinas cursadas em outra instituição pode ser solicitado na secretaria, mediante análise de ementa e carga horária equivalente a pelo menos 75% da disciplina atual.'),

('a0000000-0000-0000-0000-000000000001', 1, 'A transferência de curso ou turno pode ser solicitada uma vez por semestre, sujeita à disponibilidade de vagas, e deve ser feita até 20 dias antes do início do período letivo.'),

('a0000000-0000-0000-0000-000000000002', 1, 'O cancelamento de matrícula é definitivo e diferente do trancamento: encerra o vínculo do estudante com a instituição e não garante direito a retorno automático no futuro.'),

('a0000000-0000-0000-0000-000000000003', 1, 'O estágio obrigatório precisa ser iniciado a partir do 4º semestre, com carga horária mínima de 300 horas, supervisionado por um professor orientador e registrado no sistema de estágios.'),

('a0000000-0000-0000-0000-000000000004', 1, 'O Trabalho de Conclusão de Curso (TCC) deve ser iniciado no penúltimo semestre do curso, com orientador definido até o final do primeiro mês de aula, e entregue conforme cronograma da coordenação.'),

('a0000000-0000-0000-0000-000000000005', 1, 'O empréstimo de livros na biblioteca permite até 3 exemplares simultâneos por 14 dias, com renovação automática caso não haja fila de espera pelo título.'),

('a0000000-0000-0000-0000-000000000006', 1, 'O ASA oferece orientação de carreira, oficinas de currículo, simulações de entrevista e conexão com vagas de estágio e emprego parceiras da instituição, disponível para todos os estudantes matriculados.'),

('a0000000-0000-0000-0000-000000000007', 1, 'Faltas por motivo de saúde podem ser justificadas com atestado médico enviado em até 48 horas pelo portal do aluno, mas não isentam o estudante do conteúdo e das avaliações perdidas.'),

('a0000000-0000-0000-0000-000000000008', 1, 'A mudança de turno (manhã, tarde ou noite) pode ser solicitada uma vez por semestre, sujeita à disponibilidade de vagas na turma de destino.'),

('a0000000-0000-0000-0000-000000000009', 1, 'O certificado de conclusão fica disponível em até 30 dias após a colação de grau. O diploma físico registrado tem prazo de emissão de até 12 meses, conforme trâmite do MEC.'),

('a0000000-0000-0000-0000-000000000010', 1, 'O programa de intercâmbio permite cursar até 2 semestres em instituições parceiras no exterior, com disciplinas revalidadas automaticamente mediante aprovação prévia da coordenação.'),

('a0000000-0000-0000-0000-000000000011', 1, 'O auxílio financeiro emergencial pode ser solicitado por estudantes em situação de vulnerabilidade comprovada, com análise em até 10 dias úteis pela equipe do ASA.');
