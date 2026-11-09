# Entrega 2 · Sistemas Operacionais e Computação em Nuvem · ASA Turbo

**Endereço:** <https://54-207-148-68.sslip.io> (AWS sa-east-1). O acesso do professor está na seção 9 do relatório; as senhas foram entregues fora do repositório.

| Arquivo | Conteúdo |
|---|---|
| `relatorio_monitoramento.md` | **Relatório principal**: arquitetura, Linux, segurança, observabilidade, carga, backup, RPO/RTO, custos e limitações. Gerado a partir do `.modelo.md` por `src/Entrega 2/infra/scripts/gerar_relatorio.py` |
| `runbook_desastre.md` | Procedimento de recuperação (VM perdida) e cenários de falha |
| `politica_segredos.md` | Inventário de segredos, regras, rotação sem parada e matriz de acesso |
| `auditoria.md` | O que existia antes desta entrega |
| `diagramas/arquitetura.(mmd\|png)` | Diagrama da arquitetura (Mermaid → PNG) |
| `evidencias/vm_*.txt` | Coleta via SSH: SO, usuário, permissões, ufw, portas, SSH, fail2ban, containers, limites, systemd, journal, disco, memória, top, TLS |
| `evidencias/carga/` | k6 (JSON e texto), `docker stats` durante os testes, séries do Prometheus (CSV), `tabelas_carga.md` |
| `evidencias/backup/` | Teste de restauração em Postgres limpo, cópia externa, ensaio de desastre |
| `evidencias/falhas/` | Crash do backend, disco cheio até o alerta, reboot da VM |
| `evidencias/prints/` | Grafana antes e depois (platô de 100 VUs), Prometheus e app em produção |
| `evidencias/gitleaks.txt` | Varredura de segredos no histórico Git |

O código da infraestrutura fica em `src/Entrega 2/` (`docker-compose.yml`, `infra/`), na branch `entrega2/nuvem`.
