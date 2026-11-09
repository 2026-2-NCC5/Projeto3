#!/usr/bin/env python3
"""Preenche o relatório de monitoramento com números LIDOS dos arquivos de evidência.

    python3 infra/scripts/gerar_relatorio.py "<pasta da entrega>"

Lê <pasta>/relatorio_monitoramento.modelo.md, troca cada {{chave}} pelo valor extraído
de <pasta>/evidencias/** e grava <pasta>/relatorio_monitoramento.md. Falha (exit 1) se
algum marcador ficar sem valor: nenhum número do relatório é digitado à mão.
Só stdlib.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PASTA = Path(sys.argv[1])
EV = PASTA / "evidencias"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "loadtest"))
import tabela_comparativa as tc  # noqa: E402

tc.PASTA = EV / "carga"
V: dict[str, str] = {}


def ultimo(padrao: str, sub: str = "") -> Path:
    arqs = sorted((EV / sub).glob(padrao))
    if not arqs:
        raise SystemExit(f"sem arquivo {sub}/{padrao}")
    return arqs[-1]


def achar(arq: Path, regex: str, grupo: int = 1) -> str:
    m = re.search(regex, arq.read_text(errors="replace"), re.M)
    if not m:
        raise SystemExit(f"padrão não encontrado em {arq.name}: {regex}")
    return m.group(grupo)


def br(x: str) -> str:
    return x.replace(".", ",")


# --- carga
V["TABELA_RAMPA"] = tc.tabela_rampa("antes", "depois")
V["TABELA_ESTRESSE"] = tc.tabela_estresse([
    ("estresse_antes", "nenhum (1 worker)"),
    ("estresse_rls", "+ policies RLS com InitPlan (005)"),
    ("estresse_cache", "+ cache de 10 s da contagem da fila"),
    ("estresse_workers2", "+ UVICORN_WORKERS=2 (revertido)"),
])
a, d = tc.k6("antes"), tc.k6("depois")
V["RAMPA_REQS_ANTES"] = tc.num(tc.val(a, "http_reqs", "count"), 0)
V["RAMPA_RPS_ANTES"] = tc.num(tc.val(a, "http_reqs", "rate"), 2)
V["RAMPA_FALHA_ANTES"] = tc.pct(tc.val(a, "http_req_failed", "rate"))
V["RAMPA_FALHA_DEPOIS"] = tc.pct(tc.val(d, "http_req_failed", "rate"))
V["RAMPA_429_ANTES"] = tc.num(tc.val(a, "respostas_429", "count"), 0)
V["RAMPA_429_DEPOIS"] = tc.num(tc.val(d, "respostas_429", "count"), 0)
for rot, m in (("ANTES", a), ("DEPOIS", d)):
    V[f"CASOS_P95_{rot}"] = tc.ms(tc.val(m, "lat_fila", "p(95)"))
    V[f"CASOS_P50_{rot}"] = tc.ms(tc.val(m, "lat_fila", "med"))
    V[f"CHAT_P95_{rot}"] = tc.ms(tc.val(m, "lat_chat", "p(95)"))
V["CASOS_P95_DELTA"] = tc.delta(tc.val(a, "lat_fila", "p(95)"), tc.val(d, "lat_fila", "p(95)"))


def serie_max(rot: str, chave: str) -> float:
    return max((r[chave] for r in tc.serie(rot) if r[chave] == r[chave]), default=float("nan"))


def joelho(rot: str) -> float:
    bons = [r["rps_api"] for r in tc.serie(rot) if r["p95_api_ms"] == r["p95_api_ms"] and r["p95_api_ms"] < 500 and r["rps_api"] == r["rps_api"]]
    return max(bons) if bons else float("nan")


for rot, ch in (("estresse_antes", "EA"), ("estresse_rls", "ER"), ("estresse_cache", "EC"), ("estresse_workers2", "EW")):
    m = tc.k6(rot)
    V[f"{ch}_RPS"] = tc.num(tc.val(m, "http_reqs", "rate"), 1)
    V[f"{ch}_JOELHO"] = tc.num(joelho(rot), 1)
    V[f"{ch}_CASOS_N"] = tc.num(tc.val(m, "lat_fila", "count"), 0)
    V[f"{ch}_CPU_HOST"] = tc.num(serie_max(rot, "cpu_host_pct"), 1)
    V[f"{ch}_CPU_BACKEND"] = tc.num(serie_max(rot, "cpu_backend"), 2)
    V[f"{ch}_CPU_DB"] = tc.num(serie_max(rot, "cpu_db"), 2)
    V[f"{ch}_FALHA"] = tc.pct(tc.val(m, "http_req_failed", "rate"))
V["GANHO_JOELHO"] = tc.delta(joelho("estresse_antes"), joelho("estresse_cache"))
V["GANHO_RPS"] = tc.delta(tc.val(tc.k6("estresse_antes"), "http_reqs", "rate"), tc.val(tc.k6("estresse_cache"), "http_reqs", "rate"))
V["RAMPA_CPU_HOST_ANTES"] = tc.num(serie_max("antes", "cpu_host_pct"), 1)
V["RAMPA_CPU_HOST_DEPOIS"] = tc.num(serie_max("depois", "cpu_host_pct"), 1)
V["RAMPA_CPU_BACKEND_ANTES"] = tc.num(serie_max("antes", "cpu_backend"), 2)
V["RAMPA_CPU_DB_ANTES"] = tc.num(serie_max("antes", "cpu_db"), 2)
V["RAMPA_CPU_DB_DEPOIS"] = tc.num(serie_max("depois", "cpu_db"), 2)

# --- backup e restauração
r = ultimo("restauracao_vm_*.txt", "backup")
V["RESTORE_ARQ"] = r.name
V["RESTORE_TOTAL_S"] = br(achar(r, r"TEMPO TOTAL[^:]*: ([\d.]+) s"))
V["RESTORE_PG_S"] = br(achar(r, r"pg_restore do public: ([\d.]+) s"))
V["RESTORE_LIMPO_S"] = br(achar(r, r"Postgres limpo no ar[^:]*: ([\d.]+) s"))
V["RESTORE_RESULTADO"] = achar(r, r"RESULTADO: (.+)$")
V["RESTORE_DUMP"] = achar(r, r"# backup: (\S+ \([^)]+\))")
V["RESTORE_CONVERSAS"] = achar(r, r"conversas\s+(\d+)")
V["RESTORE_MENSAGENS"] = achar(r, r"mensagens\s+(\d+)")
V["RESTORE_USERS"] = achar(r, r"auth.users restaurados: (\d+)")
c = ultimo("copia_fora_vm_*.txt", "backup")
V["COPIA_LINHA"] = c.read_text().strip().splitlines()[-1]
dr = ultimo("ensaio_desastre_*.txt", "backup")
V["DR_ARQ"] = dr.name
V["DR_RTO_S"] = br(achar(dr, r"RTO medido[^)]*\)\s+([\d.]+) s"))
V["DR_RTO_MIN"] = br(achar(dr, r"RTO medido.*\(([\d.]+) min\)"))
V["DR_PROV_S"] = br(achar(dr, r"provisionamento \(Docker incluso\)\s+([\d.]+) s"))
V["DR_BUILD_S"] = br(achar(dr, r"build \+ banco no ar\s+([\d.]+) s"))
V["DR_RESTORE_S"] = br(achar(dr, r"^\s+restauração\s+([\d.]+) s"))
V["DR_SERVICO_S"] = br(achar(dr, r"serviço \+ certificado novo\s+([\d.]+) s"))
V["DR_COPIA_S"] = br(achar(dr, r"cópia do .env e do backup\s+([\d.]+) s"))
V["DR_SMOKE"] = achar(dr, r"Resultado: (.+)$")
V["DR_RESTORE_RESULTADO"] = achar(dr, r"RESULTADO: (.+)$")

# --- falhas
f = ultimo("falha_container_2*.txt", "falhas")
V["FALHA_CONTAINER_S"] = br(achar(f, r"200 de novo após ([\d.]+) s"))
V["FALHA_CONTAINER_RESTARTS"] = achar(f, r"RestartCount=(\d+)")
f = ultimo("falha_disco_*.txt", "falhas")
V["FALHA_DISCO_S"] = br(achar(f, r"DiscoQuaseCheio=firing \(após ([\d.]+) s\)"))
V["FALHA_DISCO_USO"] = achar(f, r"/dev/root\s+\S+\s+\S+\s+\S+\s+(8\d%|9\d%)")
f = ultimo("falha_reboot_*.txt", "falhas")
V["REBOOT_SSH_S"] = br(achar(f, r"SSH de volta após ([\d.]+) s"))
V["REBOOT_HEALTH_S"] = br(achar(f, r"health=200 após ([\d.]+) s"))

# --- segurança e VM
g = EV / "gitleaks.txt"
V["GITLEAKS_COMMITS"] = achar(g, r"(\d+) commits scanned")
V["GITLEAKS_RESULTADO"] = achar(g, r"(no leaks found|leaks found: \d+)")
vm = ultimo("vm_*.txt")
V["VM_ARQ"] = vm.name
V["VM_UNAME"] = achar(vm, r"^(Linux .+)$")
V["VM_DISTRO"] = achar(vm, r"Description:\s+(.+)$")
V["VM_ENV_PERM"] = achar(vm, r"(modo=\d+ dono=\w+ grupo=\w+) /opt/asa/.env")
V["VM_ID_ASA"] = achar(vm, r"^(uid=\d+\(asa\).*)$")
V["VM_CERT_ISSUER"] = achar(vm, r"issuer=(.+)$")
V["VM_F2B"] = achar(vm, r"Currently banned:\s+(\d+)")
V["VM_F2B_TOTAL"] = achar(vm, r"Total failed:\s+(\d+)")
V["VM_MEM"] = achar(vm, r"^Mem:\s+(\S+)")

modelo = (PASTA / "relatorio_monitoramento.modelo.md").read_text()
faltando = sorted(set(re.findall(r"\{\{(\w+)\}\}", modelo)) - V.keys())
if faltando:
    raise SystemExit(f"marcadores sem valor: {faltando}")
saida = re.sub(r"\{\{(\w+)\}\}", lambda m: V[m.group(1)], modelo)
(PASTA / "relatorio_monitoramento.md").write_text(saida)
print(f"relatorio_monitoramento.md gerado ({len(V)} valores lidos dos arquivos)")
