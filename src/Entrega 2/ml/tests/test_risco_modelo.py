"""Testes da interface RiskModel (usa só entradas sintéticas; não lê dados reais)."""

from __future__ import annotations

import sys
from itertools import pairwise
from pathlib import Path

import pytest

ML = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML))

from risco.modelo import RiskModel, explicar

ARTEFATO = ML / "artifacts" / "risco_v2.joblib"
pytestmark = pytest.mark.skipif(not ARTEFATO.exists(), reason="artefato não gerado")

BASE = {
    "tempo_de_curso": 1, "idade": 23, "mora_sp_capital": False, "total_parcelas": 12,
    "pct_parcelas_em_aberto": 0.42, "pct_parcelas_acordo": 0.1, "atraso_medio_dias": 21,
    "valor_total_periodo": 5200, "media_notas": 41, "media_assiduidade": 63, "pct_reprovacao": 0.4,
    "tendencia_notas": -12, "tendencia_assiduidade": -15, "total_semestres": 2,
    "forma_ingresso": "Vestibular", "grau_academico": "Bacharelado", "turno": "Noite", "tem_bolsa": False,
    "sexo": "Feminino", "estado_civil": "Solteiro", "total_contatos": 9, "dias_desde_ultimo_contato": 3,
}


@pytest.fixture(scope="module")
def modelo() -> RiskModel:
    return RiskModel.carregar(ARTEFATO)


def test_formato_inferencia_resultado(modelo: RiskModel) -> None:
    r = modelo.predict(BASE)
    for k in ("probabilidade", "categoria", "score", "fatores", "recomendacao", "versao_modelo", "calculado_em"):
        assert k in r
    assert 0 <= r["probabilidade"] <= 1
    assert r["categoria"] in {"verde", "amarelo", "vermelho"}
    assert set(r["score"]) == {"geral", "financeiro", "academico", "relacionamento"}
    assert r["versao_modelo"] == modelo.versao


def test_fatores_no_formato_do_contrato(modelo: RiskModel) -> None:
    fatores = modelo.explicar(BASE)
    assert 1 <= len(fatores) <= 8
    for f in fatores:
        assert set(f) == {"codigo", "descricao", "dimensao", "direcao", "peso"}
        assert f["dimensao"] in {"financeira", "academica", "relacionamento"}
        assert f["direcao"] in {"aumenta", "reduz"}
        assert 0 <= f["peso"] <= 1
    assert sum(f["peso"] for f in fatores) == pytest.approx(1, abs=0.01)
    assert explicar(BASE) == fatores


def test_sensiveis_e_contatos_nunca_como_fator(modelo: RiskModel) -> None:
    codigos = {f["codigo"] for f in modelo.explicar(BASE)}
    assert not codigos & {"sexo", "estado_civil", "idade"}
    for f in modelo.explicar(BASE):
        if f["codigo"] in {"contatos_ativos_asa", "dias_sem_contato"}:
            assert f["direcao"] == "reduz"  # regra 5


def test_sexo_e_contatos_nao_mudam_o_score(modelo: RiskModel) -> None:
    p = modelo.predict(BASE)["probabilidade"]
    outro = {**BASE, "sexo": "Masculino", "estado_civil": "Casado(a)", "total_contatos": 0, "dias_desde_ultimo_contato": 900}
    assert modelo.predict(outro)["probabilidade"] == p


@pytest.mark.parametrize("campo,valores,sentido", [
    ("pct_parcelas_em_aberto", [0.0, 0.2, 0.5, 0.9], 1),
    ("atraso_medio_dias", [-5, 0, 15, 60], 1),
    ("media_notas", [30, 50, 70, 90], -1),
    ("media_assiduidade", [50, 70, 85, 98], -1),
])
def test_monotonicidade(modelo: RiskModel, campo: str, valores: list[float], sentido: int) -> None:
    ps = [modelo.predict({**BASE, campo: v})["probabilidade"] for v in valores]
    pares = pairwise(ps)
    assert all((b - a) * sentido >= -1e-9 for a, b in pares), ps


def test_entrada_incompleta_nao_quebra(modelo: RiskModel) -> None:
    r = modelo.predict({"media_notas": 70, "pct_parcelas_em_aberto": 0.0})
    assert r["categoria"] in {"verde", "amarelo", "vermelho"}


def test_info_modelo(modelo: RiskModel) -> None:
    info = modelo.info()
    assert info["limiares"] == {"amarelo": 0.3, "vermelho": 0.6}  # contrato: const
    assert {"auc", "recall", "precisao", "f1"} <= set(info["metricas"])
