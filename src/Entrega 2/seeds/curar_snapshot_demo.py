"""Pré-calcula, com o modelo real, a trajetória da história de inadimplência da demo
e grava em seeds/demo_snapshot.json.gz (chave `curadoria_scores`).

Os seeds não trazem um vermelho com alta recente puxado por fator financeiro. Este script
faz parcelas em aberto e atraso crescerem de maio a outubro para um estudante com caso
aberto e pontua cada mês com ml/artifacts/risco_v2.joblib (ver RepoDemo._trajetoria_pontuada).
Fica pré-calculado porque o modelo leva ~0,25 s por predição e a busca faz centenas.

    docker run --rm -v "$PWD":/w -w /w/backend python:3.12-slim \\
      sh -c "pip install -q -r requirements.txt && python ../seeds/curar_snapshot_demo.py"
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "backend"))

from app.db.demo_repo import HISTORIAS, RepoDemo  # noqa: E402
from app.risk.modelo import carregar_artefato  # noqa: E402

SNAP = RAIZ / "seeds" / "demo_snapshot.json.gz"


def main() -> None:
    with gzip.open(SNAP, "rt", encoding="utf-8") as f:
        snap = json.load(f)
    snap.pop("curadoria_scores", None)
    with gzip.open(SNAP, "wt", encoding="utf-8") as f:
        json.dump(snap, f)  # sem curadoria antiga, para a busca partir dos seeds

    modelo = carregar_artefato(RAIZ / "ml" / "artifacts" / "risco_v2.joblib")
    repo = RepoDemo.__new__(RepoDemo)
    RepoDemo.__init__(repo, SNAP, modelo=None)  # carrega sem buscar
    codigos = dict((r, c) for r, c in HISTORIAS)["inadimplência"]
    repo._modelo = modelo
    achado = repo._trajetoria_pontuada(codigos, set())
    if not achado:
        sys.exit("nenhum estudante em que o modelo concorde com a história")
    eid, fator = achado
    campos = ("probabilidade", "score_financeiro", "score_academico", "score_relacionamento",
              "categoria", "fatores", "recomendacao", "versao_modelo")
    snap["curadoria_scores"] = [
        {"id": s["id"], **{k: s[k] for k in campos}}
        for s in sorted(repo.scores.values(), key=lambda s: s["competencia"]) if s["estudante_id"] == eid
    ]
    with gzip.open(SNAP, "wt", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False)
    print(eid, fator, [round(s["probabilidade"], 3) for s in snap["curadoria_scores"]])


if __name__ == "__main__":
    main()
