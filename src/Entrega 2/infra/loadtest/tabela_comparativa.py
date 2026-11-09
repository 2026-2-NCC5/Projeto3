#!/usr/bin/env python3
"""Gera as tabelas do relatório a partir dos ARQUIVOS de resultado (nunca números digitados).

    python3 infra/loadtest/tabela_comparativa.py <pasta-de-carga> > tabelas_carga.md

Lê k6_<rotulo>.json (handleSummary do k6) e series_<rotulo>.csv (exportar_series.sh).
Só stdlib.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

PASTA = Path(sys.argv[1] if len(sys.argv) > 1 else ".")


def k6(rotulo: str) -> dict:
    return json.loads((PASTA / f"k6_{rotulo}.json").read_text())["metrics"]


def val(m: dict, nome: str, chave: str) -> float:
    try:
        return float(m[nome]["values"][chave])
    except KeyError:
        return math.nan


def ms(x: float) -> str:
    return "–" if math.isnan(x) else f"{x:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x: float) -> str:
    return "–" if math.isnan(x) else f"{100 * x:.2f}".replace(".", ",") + "%"


def num(x: float, casas: int = 1) -> str:
    return "–" if math.isnan(x) else f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def delta(a: float, b: float) -> str:
    if math.isnan(a) or math.isnan(b) or a == 0:
        return "–"
    return f"{100 * (b - a) / a:+.0f}%".replace(".", ",")


def tabela_rampa(antes: str, depois: str) -> str:
    a, d = k6(antes), k6(depois)
    linhas = [
        f"| Métrica | {antes} | {depois} | Variação |",
        "|---|---:|---:|---:|",
        f"| Requisições (total) | {num(val(a, 'http_reqs', 'count'), 0)} | {num(val(d, 'http_reqs', 'count'), 0)} | {delta(val(a, 'http_reqs', 'count'), val(d, 'http_reqs', 'count'))} |",
        f"| Throughput médio (req/s) | {num(val(a, 'http_reqs', 'rate'), 2)} | {num(val(d, 'http_reqs', 'rate'), 2)} | {delta(val(a, 'http_reqs', 'rate'), val(d, 'http_reqs', 'rate'))} |",
        f"| Taxa de falha HTTP | {pct(val(a, 'http_req_failed', 'rate'))} | {pct(val(d, 'http_req_failed', 'rate'))} | |",
        f"| Taxa de 5xx | {pct(val(a, 'erros_5xx', 'rate'))} | {pct(val(d, 'erros_5xx', 'rate'))} | |",
        f"| Respostas 429 (rate limit do chat) | {num(val(a, 'respostas_429', 'count'), 0)} | {num(val(d, 'respostas_429', 'count'), 0)} | |",
    ]
    for nome, rot in [("lat_health", "/health"), ("lat_login", "login"), ("lat_chat", "/chat"), ("lat_fila", "/casos"), ("lat_caso", "/casos/{id}")]:
        for q, qn in [("med", "p50"), ("p(95)", "p95"), ("p(99)", "p99")]:
            x, y = val(a, nome, q), val(d, nome, q)
            linhas.append(f"| {rot} {qn} (ms) | {ms(x)} | {ms(y)} | {delta(x, y)} |")
    linhas.append(f"| Abstenção do chat | {pct(val(a, 'abstencoes', 'rate'))} | {pct(val(d, 'abstencoes', 'rate'))} | |")
    return "\n".join(linhas)


def serie(rotulo: str) -> list[dict]:
    p = PASTA / f"series_{rotulo}.csv"
    if not p.exists():
        return []
    with p.open() as f:
        return [{k: (float(v) if v not in ("", "nan") and k != "hora" else (v if k == "hora" else math.nan)) for k, v in r.items()} for r in csv.DictReader(f)]


def tabela_estresse(rotulos: list[tuple[str, str]]) -> str:
    linhas = [
        "| Rodada | Ajuste | Req/s (k6) | Pico de req/s (Prometheus) | Falhas | /casos atendidos | /casos p50 (ms) | /casos p95 (ms) | Último degrau com p95 < 500 ms | CPU backend (cores, máx) | CPU db (máx) | CPU host (máx) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|",
    ]
    for rot, ajuste in rotulos:
        try:
            m = k6(rot)
        except FileNotFoundError:
            continue
        s = serie(rot)
        pico = max((r["rps_api"] for r in s if not math.isnan(r["rps_api"])), default=math.nan)
        bons = [r for r in s if not math.isnan(r["p95_api_ms"]) and r["p95_api_ms"] < 500 and not math.isnan(r["rps_api"])]
        joelho = f"{num(max(r['rps_api'] for r in bons))} req/s" if bons else "–"
        mx = lambda k: max((r[k] for r in s if not math.isnan(r[k])), default=math.nan)  # noqa: E731
        linhas.append(
            f"| {rot} | {ajuste} | {num(val(m, 'http_reqs', 'rate'), 2)} | {num(pico)} | {pct(val(m, 'http_req_failed', 'rate'))} | "
            f"{num(val(m, 'lat_fila', 'count'), 0)} | {ms(val(m, 'lat_fila', 'med'))} | {ms(val(m, 'lat_fila', 'p(95)'))} | {joelho} | "
            f"{num(mx('cpu_backend'), 2)} | {num(mx('cpu_db'), 2)} | {num(mx('cpu_host_pct'))}% |"
        )
    return "\n".join(linhas)


if __name__ == "__main__":
    print("### Teste principal (rampa 10 → 50 → 100 VUs, ~9,5 min)\n")
    print(tabela_rampa("antes", "depois"))
    print("\n### Estresse (taxa de chegada crescente até saturar)\n")
    print(tabela_estresse([
        ("estresse_antes", "nenhum (1 worker)"),
        ("estresse_rls", "+ policies RLS com InitPlan (005)"),
        ("estresse_cache", "+ cache de 10 s da contagem da fila"),
        ("estresse_workers2", "+ UVICORN_WORKERS=2 (revertido)"),
    ]))
