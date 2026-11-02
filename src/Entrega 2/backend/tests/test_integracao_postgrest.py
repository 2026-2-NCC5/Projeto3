"""Integração OPCIONAL do SupabaseRepositorio contra um PostgREST real.

Pulado por padrão. Para rodar (ver backend/README.md, seção "Teste de integração"):
    ASA_TESTE_POSTGREST_URL=http://localhost:39001 \\
    ASA_TESTE_JWT_SECRET=<PGRST_JWT_SECRET> pytest tests/test_integracao_postgrest.py

Pré-requisito: banco com 001 + base de conhecimento + 002 + usuários demo + seed_demo + 003.
O teste ESCREVE no banco (conversa, feedback, validação, documento): use um banco descartável.
"""

from __future__ import annotations

import os
import time
from datetime import date

import jwt
import pytest
from postgrest import SyncPostgrestClient

from app.db.repositorio import ConflitoVersao, FiltrosFila, RegistroNaoEncontrado
from app.db.supabase_repo import SupabaseRepositorio
from tests.fakes import ID_ADMIN, ID_ATENDENTE, ID_ESTUDANTE

URL = os.environ.get("ASA_TESTE_POSTGREST_URL")
pytestmark = pytest.mark.skipif(not URL, reason="defina ASA_TESTE_POSTGREST_URL para rodar a integração")
EST_DEMO = "d0000000-0000-4000-8000-000000000001"  # no seed, estudantes.id do demo = id do perfil


@pytest.fixture(scope="module")
def repo() -> SupabaseRepositorio:
    segredo = os.environ["ASA_TESTE_JWT_SECRET"]
    tok = jwt.encode({"role": "service_role", "exp": int(time.time()) + 600}, segredo, algorithm="HS256")
    cliente = SyncPostgrestClient(URL, headers={"Authorization": f"Bearer {tok}", "apikey": tok}, timeout=10)
    return SupabaseRepositorio(cliente)  # type: ignore[arg-type]


def test_sessao(repo):
    repo.ping()
    assert repo.obter_perfil(ID_ESTUDANTE)["papel"] == "estudante"
    assert repo.obter_estudante_por_perfil(ID_ESTUDANTE)["ra"] == "99999901"
    assert repo.nomes_perfis([ID_ATENDENTE, ID_ADMIN])[ID_ADMIN]


def test_rag_listagem_e_busca(repo):
    chunks = repo.listar_chunks_ativos()
    assert len(chunks) >= 690 and chunks[0]["titulo_documento"]
    assert isinstance(repo.buscar_chunks_similares([0.01] * 1024, 3), list)  # no seed os embeddings são nulos


def test_fluxo_do_chat(repo):
    chunk = repo.listar_chunks_ativos()[0]["chunk_id"]
    salvo = repo.registrar_resposta_chat(
        {
            "estudante_id": EST_DEMO,
            "conversa_id": None,
            "resposta_id": None,
            "titulo": "Integração",
            "pergunta": "pergunta de integração",
            "resposta": "resposta",
            "confianca": 0.4,
            "abstencao": True,
            "versao_modelo": "rag-0.9+tfidf",
            "modelo_embedding": "tfidf-local",
            "latencia_ms": 10,
            "evidencias": [{"chunk_id": chunk, "similaridade": 0.4, "posicao": 1}],
            "encaminhar": True,
            "motivo_encaminhamento": "teste",
            "prazo_encaminhamento": "2026-12-01T00:00:00Z",
        }
    )
    cid = salvo["conversa_id"]
    assert salvo["encaminhamento"]["status"] == "aberto"
    assert repo.obter_conversa(cid)["status"] == "encaminhada_humano"
    assert [m["remetente"] for m in repo.historico_conversa(cid, 6)] == ["estudante", "agente"]
    msgs = repo.mensagens_conversa(cid)
    assert msgs[1]["resposta"]["fontes"][0]["titulo"]
    itens, total = repo.listar_conversas(EST_DEMO, 1, 25)
    assert total >= 1 and any(i["id"] == cid for i in itens)
    rid = str(salvo["resposta_id"])
    assert repo.dono_da_resposta(rid) == EST_DEMO
    repo.salvar_feedback(rid, EST_DEMO, "util", None)
    fb = repo.salvar_feedback(rid, EST_DEMO, "nao_util", "x")
    assert fb["avaliacao"] == "nao_util"
    with pytest.raises(RegistroNaoEncontrado):
        repo.registrar_resposta_chat(
            {
                "estudante_id": EST_DEMO,
                "conversa_id": "11111111-1111-4111-8111-111111111111",
                "pergunta": "x",
                "resposta": "y",
                "confianca": 0,
                "abstencao": True,
                "versao_modelo": "v",
                "evidencias": [],
                "encaminhar": False,
            }
        )


def test_fila_filtros_e_contagem(repo):
    p = repo.listar_fila(FiltrosFila(por_pagina=5))
    assert p.total == 300 and len(p.itens) == 5 and sum(p.contagem.values()) == 300
    ordem = {"urgente": 3, "alta": 2, "media": 1, "baixa": 0, None: -1}
    prioridades = [ordem[i["prioridade"]] for i in p.itens]
    assert prioridades == sorted(prioridades, reverse=True)
    vermelhos = repo.listar_fila(FiltrosFila(categorias=["vermelho"], por_pagina=100))
    assert all(i["categoria"] == "vermelho" for i in vermelhos.itens)
    assert vermelhos.contagem == p.contagem
    nome = p.itens[0]["nome_exibicao"]
    from app.rag.texto import normalizar

    achados = repo.listar_fila(FiltrosFila(busca=normalizar(nome)))
    assert any(i["nome_exibicao"] == nome for i in achados.itens)
    assert repo.listar_fila(FiltrosFila(responsavel="nenhum")).total > 0


def test_detalhe_validacao_e_historico(repo):
    item = repo.listar_fila(FiltrosFila(categorias=["vermelho"], status=["novo"], por_pagina=1)).itens[0]
    est = item["estudante_id"]
    assert repo.obter_item_fila(est)["score_id"] == item["score_id"]
    assert len(repo.serie_scores(est, 6)) == 6
    assert repo.obter_score(item["score_id"])["fatores"]
    with pytest.raises(ConflitoVersao):
        repo.registrar_validacao(
            {
                "estudante_id": est,
                "score_id": "11111111-1111-4111-8111-111111111111",
                "atendente_id": ID_ATENDENTE,
                "decisao": "confirmado",
                "justificativa": "Justificativa de integração longa o bastante.",
            }
        )
    v = repo.registrar_validacao(
        {
            "estudante_id": est,
            "score_id": item["score_id"],
            "atendente_id": ID_ATENDENTE,
            "decisao": "ajustado",
            "categoria_ajustada": "amarelo",
            "prioridade": "media",
            "prazo": "2026-12-01",
            "status": None,
            "assumir_caso": True,
            "justificativa": "Justificativa de integração longa o bastante.",
        }
    )
    assert v["caso_status"] == "em_acompanhamento" and v["atendente_nome"]
    depois = repo.obter_item_fila(est)
    assert depois["categoria"] == "amarelo" and depois["atendente_responsavel"] == ID_ATENDENTE
    assert repo.ultima_validacao(depois["caso_id"])["id"] == v["id"]
    hist = repo.eventos_historico(est)
    assert hist["validacoes"] and hist["scores"] and any(e["tipo"] == "status" for e in hist["eventos"])
    assert repo.estudante_existe(est) and repo.features_recentes(est)["competencia"]


def test_score_documentos_dashboard_e_auditoria(repo):
    item = repo.listar_fila(FiltrosFila(categorias=["verde"], por_pagina=1)).itens[0]
    sid = repo.registrar_score(
        {
            "estudante_id": item["estudante_id"],
            "competencia": "2026-11-01",
            "probabilidade": 0.65,
            "score_financeiro": 0.5,
            "score_academico": 0.5,
            "score_relacionamento": 0.5,
            "categoria": "vermelho",
            "fatores": [],
            "recomendacao": "Sugestão",
            "versao_modelo": "teste-integracao",
            "prioridade_sugerida": "alta",
            "usuario_id": ID_ADMIN,
        }
    )
    assert repo.obter_item_fila(item["estudante_id"])["score_id"] == sid

    emb = [0.01] * 1024
    did = repo.criar_documento(
        {
            "titulo": "Doc integração",
            "categoria": "teste",
            "fonte": "Fonte X",
            "conteudo": "conteúdo de integração v1",
            "data_atualizacao": None,
            "usuario_id": ID_ADMIN,
            "chunks": [{"conteudo": "c1", "embedding": emb}],
        }
    )
    doc = repo.obter_documento(did)
    assert doc["versao"] == 1 and doc["total_chunks"] == 1 and doc["conteudo"] == "conteúdo de integração v1"
    repo.nova_versao_documento(
        {
            "documento_id": did,
            "versao_base": 1,
            "conteudo": "v2 do conteúdo",
            "motivo": "atualização",
            "usuario_id": ID_ADMIN,
            "data_atualizacao": None,
            "chunks": [{"conteudo": "c2", "embedding": emb}],
        }
    )
    with pytest.raises(ConflitoVersao):
        repo.nova_versao_documento(
            {
                "documento_id": did,
                "versao_base": 1,
                "conteudo": "x",
                "motivo": "y",
                "usuario_id": ID_ADMIN,
                "chunks": [],
            }
        )
    doc = repo.obter_documento(did)
    assert doc["versao"] == 2 and [v["versao"] for v in doc["versoes"]] == [2, 1]
    assert doc["versoes"][0]["alterado_por"] == "Admin Demo" or doc["versoes"][0]["alterado_por"]
    itens, total = repo.listar_documentos("integracao", None, True, 1, 25)
    assert total == 1 and itens[0]["id"] == did
    repo.desativar_documento(did, "motivo de teste", ID_ADMIN)
    with pytest.raises(ConflitoVersao):
        repo.desativar_documento(did, "motivo de teste", ID_ADMIN)

    d = repo.dashboard(date(2026, 1, 1), date(2026, 12, 31))
    assert d["chat"]["perguntas"] >= 1 and sum(d["risco"]["distribuicao"].values()) == 300

    repo.registrar_auditoria(
        {
            "usuario_id": ID_ADMIN,
            "papel": "administrador",
            "acao": "teste_integracao",
            "entidade": "nenhuma",
            "entidade_id": None,
            "request_id": "itest",
            "versao": "0.9.0",
            "entrada": {"a": 1},
            "resultado": {"ok": True},
            "detalhes": None,
        }
    )


def test_ponta_a_ponta_pela_api(repo, modelo):
    """Login -> chat (fallback lexical, sem embeddings) -> fila -> detalhe -> validação -> histórico -> dashboard."""
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.rag.embeddings import CadeiaEmbeddings
    from tests.conftest import settings_teste
    from tests.contrato import validar
    from tests.fakes import SEGREDO_JWT, token

    app = create_app(
        settings_teste(supabase_jwt_secret=SEGREDO_JWT), repo=repo, embeddings=CadeiaEmbeddings([]), modelo=modelo
    )
    c = TestClient(app, raise_server_exceptions=False)
    est, ate = {"Authorization": f"Bearer {token(ID_ESTUDANTE)}"}, {"Authorization": f"Bearer {token(ID_ATENDENTE)}"}

    r = c.post("/chat", headers=est, json={"mensagem": "Como emitir o atestado de matrícula?"})
    assert r.status_code == 200, r.text
    validar("ChatResposta", r.json())
    assert r.json()["versao_modelo"].endswith("+tfidf") and r.json()["fontes"]
    r2 = c.post("/chat", headers=est, json={"mensagem": "e o horário?", "conversa_id": r.json()["conversa_id"]})
    validar("ChatResposta", r2.json())
    validar("ConversaDetalhe", c.get(f"/chat/conversas/{r.json()['conversa_id']}", headers=est).json())
    assert (
        c.post(
            "/chat/feedback", headers=est, json={"resposta_id": r.json()["resposta_id"], "avaliacao": "util"}
        ).status_code
        == 201
    )

    fila = c.get("/casos", headers=ate, params={"categoria": "vermelho", "status": "novo"}).json()
    validar("PaginaCasos", fila)
    alvo = fila["itens"][0]["estudante"]["id"]
    det = c.get(f"/casos/{alvo}", headers=ate).json()
    validar("CasoDetalhe", det)
    v = c.post(
        f"/casos/{alvo}/validacao",
        headers=ate,
        json={
            "score_id": det["score_id"],
            "decisao": "confirmado",
            "justificativa": "Estudante confirmou dificuldade financeira no contato.",
        },
    )
    assert v.status_code == 201, v.text
    validar("Validacao", v.json())
    validar("PaginaHistorico", c.get(f"/casos/{alvo}/historico", headers=ate).json())
    adm = {"Authorization": f"Bearer {token(ID_ADMIN)}"}
    dash = c.get("/admin/dashboard", headers=adm, params={"de": "2026-01-01", "ate": "2026-12-31"})
    validar("Dashboard", dash.json())
    validar("PaginaDocumentos", c.get("/admin/documentos", headers=adm, params={"busca": "atestado"}).json())
    validar("Saude", c.get("/health").json())
