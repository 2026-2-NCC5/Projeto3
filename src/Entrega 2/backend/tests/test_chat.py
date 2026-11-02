"""POST /chat e afins: contrato, abstenção com encaminhamento, contexto, persistência e auditoria."""

from __future__ import annotations

from tests.contrato import validar
from tests.fakes import (
    CHUNK_ATESTADO,
    CHUNK_ATESTADO_LOCAL,
    CHUNK_TRANCAMENTO,
    CHUNK_TRANCAMENTO_PRAZO,
    ID_ESTUDANTE,
    ID_OUTRO_ESTUDANTE,
    auth,
)

H = auth(ID_ESTUDANTE)


def _perguntar(amb, mensagem, **extra):
    return amb.client.post("/chat", headers=H, json={"mensagem": mensagem, **extra})


def test_resposta_com_fontes_e_data_no_formato_do_contrato(amb):
    amb.repo.busca_resultado = [
        amb.repo.resultado(CHUNK_ATESTADO, 0.71),
        amb.repo.resultado(CHUNK_ATESTADO_LOCAL, 0.58),
    ]
    r = _perguntar(amb, "Como tiro o atestado de matrícula?")
    assert r.status_code == 200
    corpo = r.json()
    validar("ChatResposta", corpo)
    assert not corpo["abstencao"] and corpo["motivo_abstencao"] is None and corpo["encaminhamento"] is None
    assert corpo["confianca"] == 0.71
    assert corpo["versao_modelo"] == "rag-0.9+bge-m3"
    fonte = corpo["fontes"][0]
    assert fonte["titulo"] == "Atestado de matrícula" and fonte["fonte"].startswith("Cesta de Serviços")
    assert fonte["data_atualizacao"].startswith("2026-10-15")
    assert "Portal do Aluno" in corpo["resposta"]
    assert r.headers["X-Request-ID"]


def test_abstencao_abaixo_do_limiar_encaminha_para_humano(amb):
    amb.repo.busca_resultado = [amb.repo.resultado(CHUNK_ATESTADO, 0.42)]
    r = _perguntar(amb, "Posso levar meu cachorro para a aula?")
    corpo = r.json()
    validar("ChatResposta", corpo)
    assert corpo["abstencao"] and corpo["motivo_abstencao"] == "baixa_similaridade"
    assert corpo["encaminhamento"]["status"] == "aberto" and corpo["encaminhamento"]["setor_destino"] == "ASA"
    assert "ASA" in corpo["resposta"]
    assert "Portal do Aluno" not in corpo["resposta"]  # não usa o trecho fraco como resposta
    assert corpo["fontes"][0]["similaridade"] == 0.42  # candidato fraco aparece como fonte
    conversa = amb.repo.conversas[corpo["conversa_id"]]
    assert conversa["status"] == "encaminhada_humano"


def test_segunda_abstencao_reaproveita_o_encaminhamento_aberto(amb):
    r1 = _perguntar(amb, "Posso levar meu cachorro?").json()
    r2 = _perguntar(amb, "E meu gato?", conversa_id=r1["conversa_id"]).json()
    assert r1["encaminhamento"]["id"] == r2["encaminhamento"]["id"]
    assert len(amb.repo.encaminhamentos) == 1


def test_contexto_da_conversa_reescreve_pergunta_de_continuacao(amb):
    amb.repo.busca_resultado = [amb.repo.resultado(CHUNK_TRANCAMENTO, 0.7)]
    r1 = _perguntar(amb, "Como faço o trancamento de matrícula?").json()
    amb.provedor.chamadas.clear()
    amb.repo.busca_resultado = [amb.repo.resultado(CHUNK_TRANCAMENTO_PRAZO, 0.66)]
    r2 = _perguntar(amb, "e o prazo?", conversa_id=r1["conversa_id"]).json()
    consulta = amb.provedor.chamadas[0][0]
    assert "trancamento de matrícula" in consulta and "prazo" in consulta
    assert r2["conversa_id"] == r1["conversa_id"] and not r2["abstencao"]
    assert "1. O prazo do trancamento" in r2["resposta"]  # enumeração vira passos numerados
    audit = amb.repo.auditoria[-1]
    assert audit["entrada"]["reescrita"] is True and audit["entrada"]["pergunta"] == "e o prazo?"


def test_contexto_enviado_pelo_cliente_vale_para_conversa_nova(amb):
    _perguntar(
        amb,
        "e o prazo?",
        historico=[
            {"papel": "estudante", "conteudo": "Como faço o trancamento de matrícula?"},
            {"papel": "agente", "conteudo": "Pelo Portal do Aluno."},
        ],
    )
    assert "trancamento" in amb.provedor.chamadas[-1][0]


def test_persiste_conversa_mensagens_resposta_evidencias_e_auditoria(amb):
    amb.repo.busca_resultado = [amb.repo.resultado(CHUNK_ATESTADO, 0.71)]
    corpo = _perguntar(amb, "Como tiro o atestado?").json()
    resp = amb.repo.respostas[corpo["resposta_id"]]
    assert resp["evidencias"] == [{"chunk_id": CHUNK_ATESTADO, "similaridade": 0.71, "posicao": 1}]
    assert resp["modelo_embedding"] == "@cf/baai/bge-m3" and resp["latencia_ms"] >= 0
    assert [m["remetente"] for m in amb.repo.mensagens] == ["estudante", "agente"]
    a = amb.repo.auditoria[-1]
    assert a["acao"] == "resposta_gerada" and a["usuario_id"] == ID_ESTUDANTE and a["papel"] == "estudante"
    assert a["request_id"] and a["versao"] == "rag-0.9+bge-m3"
    assert a["resultado"]["chunks"] == [CHUNK_ATESTADO]


def test_conversa_de_outra_pessoa_e_404(amb):
    corpo = _perguntar(amb, "Como tiro o atestado?").json()
    outro = auth(ID_OUTRO_ESTUDANTE)
    r = amb.client.post("/chat", headers=outro, json={"mensagem": "oi", "conversa_id": corpo["conversa_id"]})
    assert r.status_code == 404 and r.json()["codigo"] == "nao_encontrado"
    assert amb.client.get(f"/chat/conversas/{corpo['conversa_id']}", headers=outro).status_code == 404
    lista = amb.client.get("/chat/conversas", headers=outro).json()
    assert lista["total"] == 0


def test_listar_e_detalhar_conversa(amb):
    amb.repo.busca_resultado = [amb.repo.resultado(CHUNK_ATESTADO, 0.71)]
    corpo = _perguntar(amb, "Como tiro o atestado?").json()
    lista = amb.client.get("/chat/conversas", headers=H).json()
    validar("PaginaConversas", lista)
    assert lista["total"] == 1 and lista["itens"][0]["titulo"] == "Como tiro o atestado?"
    det = amb.client.get(f"/chat/conversas/{corpo['conversa_id']}", headers=H).json()
    validar("ConversaDetalhe", det)
    agente = det["mensagens"][1]
    assert agente["remetente"] == "agente" and agente["resposta"]["fontes"][0]["titulo"] == "Atestado de matrícula"


def test_feedback_util_nao_util_substitui_o_anterior(amb):
    corpo = _perguntar(amb, "Como tiro o atestado?").json()
    for avaliacao in ("util", "nao_util"):
        r = amb.client.post(
            "/chat/feedback", headers=H, json={"resposta_id": corpo["resposta_id"], "avaliacao": avaliacao}
        )
        assert r.status_code == 201
        validar("Feedback", r.json())
    assert [f["avaliacao"] for f in amb.repo.feedbacks] == ["nao_util"]
    det = amb.client.get(f"/chat/conversas/{corpo['conversa_id']}", headers=H).json()
    assert det["mensagens"][1]["resposta"]["feedback"] == "nao_util"
    assert amb.repo.auditoria[-1]["acao"] == "feedback_resposta"


def test_feedback_em_resposta_alheia_ou_inexistente_e_404(amb):
    corpo = _perguntar(amb, "Como tiro o atestado?").json()
    r = amb.client.post(
        "/chat/feedback",
        headers=auth(ID_OUTRO_ESTUDANTE),
        json={"resposta_id": corpo["resposta_id"], "avaliacao": "util"},
    )
    assert r.status_code == 404
    r = amb.client.post(
        "/chat/feedback", headers=H, json={"resposta_id": "11111111-1111-4111-8111-111111111111", "avaliacao": "util"}
    )
    assert r.status_code == 404


def test_validacao_da_pergunta(amb):
    r = amb.client.post("/chat", headers=H, json={"mensagem": ""})
    assert r.status_code == 422 and r.json()["codigo"] == "validacao"
    assert r.json()["detalhes"][0]["campo"] == "mensagem"
    r = amb.client.post("/chat", headers=H, json={"mensagem": "   "})
    assert r.status_code == 422
    r = amb.client.post("/chat", headers=H, json={"mensagem": "x" * 1001})
    assert r.status_code == 422
    r = amb.client.post("/chat", headers={**H, "Content-Type": "application/json"}, content=b"{nao json")
    assert r.status_code == 400 and r.json()["codigo"] == "requisicao_invalida"


def test_limite_de_mensagens_por_minuto(amb):
    amb.app.state.servico_chat.limitador._limite = 2
    assert _perguntar(amb, "a pergunta um").status_code == 200
    assert _perguntar(amb, "a pergunta dois").status_code == 200
    r = _perguntar(amb, "a pergunta tres")
    assert r.status_code == 429 and r.json()["codigo"] == "limite_excedido"
    assert int(r.headers["Retry-After"]) >= 1


def test_banco_fora_ao_salvar_ainda_responde_ao_estudante(amb):
    amb.repo.busca_resultado = [amb.repo.resultado(CHUNK_ATESTADO, 0.71)]
    amb.repo.falhar.add("registrar_resposta_chat")
    r = _perguntar(amb, "Como tiro o atestado?")
    assert r.status_code == 200 and not r.json()["abstencao"]
