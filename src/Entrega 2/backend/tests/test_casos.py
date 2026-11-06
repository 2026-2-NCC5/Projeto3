"""Contrato de resposta de /casos (fila, detalhe, histórico)."""

from __future__ import annotations

from tests.contrato import validar
from tests.fakes import CASO_RISCO, EST_RISCO, EST_VERDE, ID_ADMIN, ID_ATENDENTE, SCORE_RISCO, auth

H = auth(ID_ATENDENTE)


def test_fila_no_formato_do_contrato_e_ordenada_por_prioridade(amb):
    r = amb.client.get("/casos", headers=H)
    assert r.status_code == 200
    corpo = r.json()
    validar("PaginaCasos", corpo)
    assert corpo["total"] == 2 and corpo["pagina"] == 1 and corpo["por_pagina"] == 25
    assert corpo["contagem"] == {"verde": 1, "amarelo": 0, "vermelho": 1}
    primeiro, segundo = corpo["itens"]
    assert primeiro["estudante"]["id"] == EST_RISCO and primeiro["prioridade"] == "alta"
    assert primeiro["tendencia"] == "subindo" and primeiro["variacao"] == 0.11
    # verde sem caso aberto: caso_id/status/prioridade nulos (contrato)
    assert segundo["estudante"]["id"] == EST_VERDE and segundo["caso_id"] is None and segundo["status"] is None


def test_filtros_da_fila(amb):
    def ids(params):
        return [i["estudante"]["id"] for i in amb.client.get("/casos", headers=H, params=params).json()["itens"]]

    assert ids({"categoria": ["vermelho"]}) == [EST_RISCO]
    assert ids({"categoria": ["verde", "amarelo"]}) == [EST_VERDE]
    assert ids({"prioridade": "alta"}) == [EST_RISCO]
    assert ids({"status": "novo"}) == [EST_RISCO]
    assert ids({"busca": "caio antunes"}) == [EST_RISCO]
    assert ids({"busca": "LIVIA ARAUJO"}) == [EST_VERDE]  # sem acento
    assert ids({"busca": "99000111"}) == [EST_RISCO]
    assert ids({"responsavel": "eu"}) == []
    assert ids({"ordenar": "score"}) == [EST_VERDE, EST_RISCO]
    # contagem ignora o filtro de categoria (contadores da fila)
    corpo = amb.client.get("/casos", headers=H, params={"categoria": "vermelho"}).json()
    assert corpo["contagem"] == {"verde": 1, "amarelo": 0, "vermelho": 1}


def test_parametros_invalidos_na_fila_sao_400(amb):
    for params in (
        {"categoria": "roxo"},
        {"pagina": 0},
        {"por_pagina": 101},
        {"pagina": "abc"},
        {"ordenar": "aleatorio"},
    ):
        r = amb.client.get("/casos", headers=H, params=params)
        assert r.status_code == 400, params
        validar("Erro", r.json())
        assert r.json()["codigo"] == "requisicao_invalida"


def test_detalhe_do_caso_no_formato_do_contrato(amb):
    r = amb.client.get(f"/casos/{EST_RISCO}", headers=H)
    assert r.status_code == 200
    corpo = r.json()
    validar("CasoDetalhe", corpo)
    assert corpo["score_id"] == SCORE_RISCO
    assert corpo["score"] == {"geral": 0.72, "financeiro": 0.8, "academico": 0.6, "relacionamento": 0.3}
    assert corpo["categoria"] == "vermelho" and corpo["versao_modelo"] == "seed-sintetico-0"
    assert corpo["aviso"] == "Apoio à decisão. Nenhuma ação deve ser tomada sem avaliação humana."
    # tendência: 6 meses, do mais antigo ao mais recente
    assert [p["competencia"] for p in corpo["tendencia"]] == [f"2026-{m:02d}-01" for m in range(5, 11)]
    # atributo sensível nunca aparece como fator; pesos renormalizados
    assert "sexo" not in {f["codigo"] for f in corpo["fatores"]}
    assert abs(sum(f["peso"] for f in corpo["fatores"]) - 1) < 0.02
    # recomendação por regra: vermelho + pendência financeira -> orientação sobre acordo
    assert corpo["recomendacao"].startswith("Sugestão:") and "acordo" in corpo["recomendacao"]
    assert corpo["caso"]["id"] == CASO_RISCO and corpo["caso"]["status"] == "novo"
    assert corpo["ultima_validacao"] is None


def test_detalhe_de_estudante_verde_sem_caso(amb):
    corpo = amb.client.get(f"/casos/{EST_VERDE}", headers=auth(ID_ADMIN)).json()
    validar("CasoDetalhe", corpo)
    assert corpo["caso"]["id"] is None and corpo["recomendacao"].startswith("Sem ação imediata")


def test_caso_inexistente_404_e_id_invalido_400(amb):
    r = amb.client.get("/casos/11111111-1111-4111-8111-111111111111", headers=H)
    assert r.status_code == 404 and r.json()["codigo"] == "nao_encontrado"
    assert amb.client.get("/casos/nao-e-uuid", headers=H).status_code == 400


def test_historico_do_caso(amb):
    r = amb.client.get(f"/casos/{EST_RISCO}/historico", headers=H)
    assert r.status_code == 200
    corpo = r.json()
    validar("PaginaHistorico", corpo)
    tipos = [e["tipo"] for e in corpo["itens"]]
    assert {"score", "criado", "contato"} <= set(tipos)
    datas = [e["ocorrido_em"] for e in corpo["itens"]]
    assert datas == sorted(datas, reverse=True)
    pag = amb.client.get(f"/casos/{EST_RISCO}/historico", headers=H, params={"por_pagina": 2}).json()
    assert len(pag["itens"]) == 2 and pag["total"] == corpo["total"]


def test_banco_fora_na_fila_vira_503(amb):
    amb.repo.falhar.add("listar_fila")
    r = amb.client.get("/casos", headers=H)
    assert r.status_code == 503 and r.json()["codigo"] == "indisponivel"
