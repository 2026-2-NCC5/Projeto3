"""Validação humana: decisão + justificativa, status do caso, concorrência e auditoria."""

from __future__ import annotations

import pytest
from prometheus_client import REGISTRY

from tests.contrato import validar
from tests.fakes import CASO_RISCO, EST_RISCO, EST_VERDE, ID_ATENDENTE, SCORE_RISCO, SCORE_VERDE, auth

H = auth(ID_ATENDENTE)
JUST = "Conversei com o estudante e a pendência financeira se confirma."


def _validar(amb, estudante=EST_RISCO, **corpo):
    base = {"score_id": SCORE_RISCO, "decisao": "confirmado", "justificativa": JUST}
    return amb.client.post(f"/casos/{estudante}/validacao", headers=H, json={**base, **corpo})


def test_confirmar_registra_decisao_e_atualiza_caso(amb):
    antes = REGISTRY.get_sample_value("validacoes_total", {"decisao": "confirmado"}) or 0
    r = _validar(amb)
    assert r.status_code == 201
    corpo = r.json()
    validar("Validacao", corpo)
    assert corpo["decisao"] == "confirmado" and corpo["atendente"]["nome"] == "Atendente Demo"
    assert corpo["versao_modelo"] == "seed-sintetico-0" and corpo["score_id"] == SCORE_RISCO
    caso = amb.repo.casos[CASO_RISCO]
    assert caso["status"] == "em_acompanhamento" and caso["atendente_responsavel"] == ID_ATENDENTE
    assert REGISTRY.get_sample_value("validacoes_total", {"decisao": "confirmado"}) == antes + 1
    # auditoria com usuário, versão, entrada (justificativa) e resultado
    a = amb.repo.auditoria[-1]
    assert a["acao"] == "validacao_humana" and a["usuario_id"] == ID_ATENDENTE
    assert a["entrada"]["justificativa"] == JUST and a["versao"] == "seed-sintetico-0"
    # aparece no detalhe e no histórico
    det = amb.client.get(f"/casos/{EST_RISCO}", headers=H).json()
    assert det["ultima_validacao"]["id"] == corpo["id"]
    hist = amb.client.get(f"/casos/{EST_RISCO}/historico", headers=H).json()
    assert hist["itens"][0]["tipo"] in ("validacao", "status", "responsavel")
    assert any(e["tipo"] == "validacao" for e in hist["itens"])


def test_ajustar_exige_categoria_e_muda_a_categoria_vigente(amb):
    r = _validar(amb, decisao="ajustado")
    assert r.status_code == 422 and r.json()["codigo"] == "validacao"
    r = _validar(amb, decisao="ajustado", categoria_ajustada="amarelo", prioridade="media", prazo="2026-11-20")
    assert r.status_code == 201 and r.json()["categoria_ajustada"] == "amarelo"
    det = amb.client.get(f"/casos/{EST_RISCO}", headers=H).json()
    assert det["categoria"] == "amarelo" and det["categoria_modelo"] == "vermelho"
    assert det["caso"]["prioridade"] == "media" and det["caso"]["prazo"] == "2026-11-20"


def test_rejeitar_arquiva_o_caso_salvo_se_status_informado(amb):
    assert _validar(amb, decisao="rejeitado").status_code == 201
    assert amb.repo.casos[CASO_RISCO]["status"] == "arquivado"
    assert amb.repo.casos[CASO_RISCO]["categoria_vigente"] == "verde"
    assert _validar(amb, decisao="rejeitado", status="contatado").status_code == 201
    assert amb.repo.casos[CASO_RISCO]["status"] == "contatado"


@pytest.mark.parametrize("justificativa", ["", "curta demais", " " * 30, "a" * 2001])
def test_justificativa_obrigatoria_com_minimo_de_20_caracteres(amb, justificativa):
    for decisao in ("ajustado", "rejeitado", "confirmado"):
        r = _validar(amb, decisao=decisao, categoria_ajustada="amarelo", justificativa=justificativa)
        assert r.status_code == 422, (decisao, justificativa)
        validar("Erro", r.json())
        assert r.json()["detalhes"]
    assert amb.repo.validacoes == []


def test_score_desatualizado_responde_409(amb):
    r = _validar(amb, score_id=SCORE_VERDE)
    assert r.status_code == 409 and r.json()["codigo"] == "conflito"
    assert "Recarregue" in r.json()["mensagem"]
    assert amb.repo.validacoes == []


def test_estudante_inexistente_404(amb):
    r = _validar(amb, estudante="11111111-1111-4111-8111-111111111111")
    assert r.status_code == 404


def test_validar_estudante_sem_caso_abre_caso(amb):
    r = _validar(amb, estudante=EST_VERDE, score_id=SCORE_VERDE, assumir_caso=False)
    assert r.status_code == 201
    caso = next(c for c in amb.repo.casos.values() if c["estudante_id"] == EST_VERDE)
    assert caso["atendente_responsavel"] is None


def test_nada_e_executado_automaticamente(amb):
    """A validação só registra decisão e estado do caso: nenhum contato, mensagem ou ação é criado."""
    contatos, conversas = len(amb.repo.contatos), len(amb.repo.conversas)
    _validar(amb, decisao="confirmado")
    assert len(amb.repo.contatos) == contatos and len(amb.repo.conversas) == conversas
