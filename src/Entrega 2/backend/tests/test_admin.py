"""Admin: dashboard agregado e base de conhecimento (cadastrar, versionar, desativar)."""

from __future__ import annotations

from tests.contrato import validar
from tests.fakes import CHUNK_ATESTADO, ID_ADMIN, ID_ESTUDANTE, auth

H = auth(ID_ADMIN)
DOC = {
    "titulo": "Regulamento de Estágio",
    "categoria": "carreira_empregabilidade",
    "fonte": "Regulamento Acadêmico - Art. 40",
    "conteudo": "O estágio obrigatório exige termo de compromisso assinado.\n\nO prazo de entrega é de 30 dias.",
}


def test_dashboard_agregado(amb):
    amb.repo.busca_resultado = [amb.repo.resultado(CHUNK_ATESTADO, 0.4)]
    amb.client.post("/chat", headers=auth(ID_ESTUDANTE), json={"mensagem": "Posso levar meu cachorro?"})
    r = amb.client.get("/admin/dashboard", headers=H)
    assert r.status_code == 200
    corpo = r.json()
    validar("Dashboard", corpo)
    assert corpo["chat"]["perguntas"] == 1 and corpo["chat"]["taxa_abstencao"] == 1
    assert corpo["risco"]["distribuicao"] == {"verde": 1, "amarelo": 0, "vermelho": 1}
    assert corpo["encaminhamentos"]["abertos"] == 1


def test_dashboard_periodo_invalido(amb):
    r = amb.client.get("/admin/dashboard", headers=H, params={"de": "2026-11-10", "ate": "2026-11-01"})
    assert r.status_code == 400
    r = amb.client.get("/admin/dashboard", headers=H, params={"de": "ontem"})
    assert r.status_code == 400


def test_cadastrar_documento_gera_chunks_com_embedding(amb):
    r = amb.client.post("/admin/documentos", headers=H, json=DOC)
    assert r.status_code == 201
    corpo = r.json()
    validar("DocumentoDetalhe", corpo)
    assert corpo["versao"] == 1 and corpo["ativo"] and corpo["total_chunks"] >= 1
    assert corpo["chunks_sem_embedding"] == 0 and corpo["conteudo"] == DOC["conteudo"]
    assert amb.provedor.chamadas  # vetorizou antes de gravar
    assert amb.repo.auditoria[-1]["acao"] == "documento_cadastrado"
    lista = amb.client.get("/admin/documentos", headers=H).json()
    validar("PaginaDocumentos", lista)
    assert lista["total"] == 1


def test_cadastro_com_vetorizacao_fora_e_503_e_nada_e_gravado(amb):
    amb.provedor.falhar = amb.reserva.falhar = True
    r = amb.client.post("/admin/documentos", headers=H, json=DOC)
    assert r.status_code == 503 and r.json()["codigo"] == "indisponivel"
    assert amb.repo.documentos == {}


def test_nova_versao_reindexa_e_controla_concorrencia(amb):
    doc = amb.client.post("/admin/documentos", headers=H, json=DOC).json()
    nova = {
        "versao_base": 1,
        "conteudo": "Texto novo do regulamento de estágio, revisado.",
        "motivo": "Atualização do prazo",
    }
    r = amb.client.post(f"/admin/documentos/{doc['id']}/versoes", headers=H, json=nova)
    assert r.status_code == 201
    corpo = r.json()
    validar("DocumentoDetalhe", corpo)
    assert corpo["versao"] == 2 and corpo["conteudo"] == nova["conteudo"]
    assert [v["versao"] for v in corpo["versoes"]] == [2, 1]
    assert corpo["versoes"][0]["alterado_por"] == "Admin Demo"
    ativos = [c for c in amb.repo.chunks_docs if c["documento_id"] == doc["id"] and c["ativo"]]
    assert ativos and all(c["embedding"] for c in ativos)
    assert any(not c["ativo"] for c in amb.repo.chunks_docs)  # chunks antigos preservados (inativos)
    r = amb.client.post(f"/admin/documentos/{doc['id']}/versoes", headers=H, json=nova)  # versao_base velha
    assert r.status_code == 409


def test_desativar_documento(amb):
    doc = amb.client.post("/admin/documentos", headers=H, json=DOC).json()
    r = amb.client.post(f"/admin/documentos/{doc['id']}/desativar", headers=H, json={"motivo": "curto"})
    assert r.status_code == 422
    r = amb.client.post(
        f"/admin/documentos/{doc['id']}/desativar", headers=H, json={"motivo": "Regulamento revogado em 2026"}
    )
    assert r.status_code == 200
    validar("DocumentoDetalhe", r.json())
    assert r.json()["ativo"] is False and r.json()["motivo_desativacao"] == "Regulamento revogado em 2026"
    r = amb.client.post(
        f"/admin/documentos/{doc['id']}/desativar", headers=H, json={"motivo": "Regulamento revogado em 2026"}
    )
    assert r.status_code == 409
    assert amb.client.get("/admin/documentos/11111111-1111-4111-8111-111111111111", headers=H).status_code == 404
