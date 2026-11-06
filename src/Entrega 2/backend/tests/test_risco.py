"""Modelo de risco (interface RiskModel), recomendação por regra e rotas /risco."""

from __future__ import annotations

import joblib
import pytest

from app.risk.modelo import ModeloML, ModeloSklearn, carregar_modelo, categoria_de
from app.risk.recomendacao import prioridade_sugerida, recomendar, tendencia_de
from tests.contrato import validar
from tests.fakes import EST_RISCO, ID_ADMIN, ID_ATENDENTE, ID_TECNICO, auth

FEATURES = {
    "tempo_de_curso": 3,
    "total_parcelas": 20,
    "pct_parcelas_em_aberto": 0.4,
    "pct_parcelas_acordo": 0.1,
    "atraso_medio_dias": 30,
    "media_notas": 55,
    "media_assiduidade": 70,
    "pct_reprovacao": 0.3,
    "total_semestres": 3,
    "sexo": "Feminino",
    "idade": 30,
    "estado_civil": "Casado(a)",
}


def test_predict_devolve_score_categoria_fatores(modelo: ModeloML):
    p = modelo.predict(FEATURES)
    assert 0 <= p.probabilidade <= 1 and p.categoria == categoria_de(p.probabilidade)
    assert set(p.score) == {"geral", "financeiro", "academico", "relacionamento"}
    assert all(0 <= v <= 1 for v in p.score.values())
    assert 0 < len(p.fatores) <= 8
    assert abs(sum(f["peso"] for f in p.fatores) - 1) < 0.05
    for f in p.fatores:
        assert f["direcao"] in ("aumenta", "reduz") and f["dimensao"] in ("financeira", "academica", "relacionamento")
        assert f["codigo"] not in ("sexo", "idade", "estado_civil")
        assert "R$" not in f["descricao"]  # nunca valor monetário exato


def test_contribuicoes_tem_sinal_coerente_com_a_probabilidade(modelo: ModeloML):
    ruim = modelo.predict({**FEATURES, "media_notas": 20, "media_assiduidade": 40})
    bom = modelo.predict({**FEATURES, "media_notas": 95, "media_assiduidade": 99})
    assert ruim.score["academico"] > bom.score["academico"]


def test_faixas_de_categoria():
    assert categoria_de(0.29) == "verde" and categoria_de(0.30) == "amarelo"
    assert categoria_de(0.5999) == "amarelo" and categoria_de(0.60) == "vermelho"


def test_recomendacao_por_regra_e_sempre_sugestao():
    fin = [{"codigo": "parcelas_em_aberto", "dimensao": "financeira", "direcao": "aumenta", "peso": 0.6}]
    acad = [{"codigo": "assiduidade", "dimensao": "academica", "direcao": "aumenta", "peso": 0.7}]
    r = recomendar("vermelho", fin)
    assert r.startswith("Sugestão:") and "acordo" in r and "ASA" in r and r.endswith("A decisão é do atendente.")
    assert "monitoria" in recomendar("amarelo", acad)
    assert recomendar("verde", fin).startswith("Sem ação imediata")
    for cat in ("amarelo", "vermelho"):
        for fat in (fin, acad, []):
            texto = recomendar(cat, fat).lower()
            for proibido in ("cancelar", "bloquear", "suspender", "desligar", "cobrança judicial"):
                assert proibido not in texto


def test_prioridade_e_tendencia():
    assert prioridade_sugerida("vermelho", "subindo") == "urgente"
    assert prioridade_sugerida("vermelho") == "alta"
    assert tendencia_de(0.7, 0.6) == "subindo" and tendencia_de(0.5, 0.6) == "caindo"
    assert tendencia_de(0.62, 0.6) == "estavel" and tendencia_de(0.6, None) == "estavel"


def test_artefato_final_usa_o_modelo_da_sessao_de_ml(modelo: ModeloML):
    assert isinstance(modelo, ModeloML) and modelo.versao == "risco-2.0.0"
    info = modelo.info()
    assert not {"idade", "sexo", "estado_civil"} & set(info["features"])
    ruim = modelo.predict({**FEATURES, "pct_parcelas_em_aberto": 0.9, "atraso_medio_dias": 120, "media_notas": 15})
    assert ruim.categoria in ("amarelo", "vermelho") and any(f["direcao"] == "aumenta" for f in ruim.fatores)
    assert ruim.probabilidade > modelo.predict(FEATURES).probabilidade


def test_carrega_artefato_dict_simples(tmp_path, placeholder: ModeloSklearn):
    caminho = tmp_path / "modelo_risco.joblib"
    joblib.dump(
        {
            "modelo": placeholder._est,
            "features": placeholder.features,
            "referencia": placeholder.referencia,
            "versao": "rl-baseline-1.0",
            "algoritmo": "Regressão Logística",
            "treinado_em": "2026-11-03T12:00:00-03:00",
            "metricas": {"auc": 0.82, "recall": 0.77},
        },
        caminho,
    )
    m = carregar_modelo(caminho, tmp_path / "nao-existe.csv")
    assert m is not None and m.versao == "rl-baseline-1.0"
    assert m.predict(FEATURES).versao_modelo == "rl-baseline-1.0"


def test_artefato_invalido_cai_no_placeholder(tmp_path):
    from app.core.config import PROJETO_DIR

    caminho = tmp_path / "ruim.joblib"
    joblib.dump({"formato": "errado"}, caminho)
    m = carregar_modelo(caminho, PROJETO_DIR / "seeds" / "estudantes_sinteticos.csv")
    assert m is not None and m.versao.startswith("rl-placeholder")


def test_sem_artefato_e_sem_seeds_nao_ha_modelo(tmp_path):
    assert carregar_modelo(tmp_path / "x.joblib", tmp_path / "y.csv") is None


# ------------------------------------------------------------------ rotas
def test_modelo_info_no_contrato(amb):
    r = amb.client.get("/risco/modelo", headers=auth(ID_ATENDENTE))
    assert r.status_code == 200
    validar("ModeloInfo", r.json())
    assert r.json()["limiares"] == {"amarelo": 0.3, "vermelho": 0.6}
    assert "sexo" not in r.json()["features"]


@pytest.mark.parametrize("uid", [ID_ADMIN, ID_TECNICO])
def test_inferir_simulacao_nao_grava(amb, uid):
    n = len(amb.repo.scores)
    r = amb.client.post("/risco/inferir", headers=auth(uid), json={"features": FEATURES})
    assert r.status_code == 200
    corpo = r.json()
    validar("InferenciaResultado", corpo)
    assert corpo["persistido"] is False and corpo["score_id"] is None
    assert len(amb.repo.scores) == n
    assert amb.repo.auditoria[-1]["acao"] == "inferencia_risco"


def test_inferir_com_estudante_e_persistir(amb):
    r = amb.client.post("/risco/inferir", headers=auth(ID_ADMIN), json={"estudante_id": EST_RISCO, "persistir": True})
    corpo = r.json()
    validar("InferenciaResultado", corpo)
    assert corpo["persistido"] and corpo["score_id"] in amb.repo.scores
    assert corpo["versao_modelo"] == "risco-2.0.0"


def test_inferir_entrada_invalida(amb):
    h = auth(ID_ADMIN)
    assert amb.client.post("/risco/inferir", headers=h, json={}).status_code == 422
    assert (
        amb.client.post("/risco/inferir", headers=h, json={"estudante_id": EST_RISCO, "features": FEATURES}).status_code
        == 422
    )
    assert (
        amb.client.post("/risco/inferir", headers=h, json={"features": FEATURES, "persistir": True}).status_code == 422
    )
    r = amb.client.post("/risco/inferir", headers=h, json={"estudante_id": "11111111-1111-4111-8111-111111111111"})
    assert r.status_code == 404


def test_sem_modelo_responde_503(amb):
    amb.app.state.servico_risco.modelo = None
    r = amb.client.get("/risco/modelo", headers=auth(ID_TECNICO))
    assert r.status_code == 503 and r.json()["codigo"] == "indisponivel"
