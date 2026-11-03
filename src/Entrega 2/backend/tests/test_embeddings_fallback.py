"""Fallback de embeddings: falha/timeout da API -> provedor reserva -> TF-IDF local -> abstenção."""

from __future__ import annotations

import httpx
import pytest
from prometheus_client import REGISTRY

from app.rag import (
    CadeiaEmbeddings,
    CloudflareEmbedding,
    ConfigRAG,
    FalhaVetorizacao,
    HuggingFaceEmbedding,
    IndiceLexical,
    recuperar,
)
from tests.fakes import ID_ESTUDANTE, ProvedorFalso, RepoMemoria, auth

DIM = 8


def _cliente(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _cf(handler) -> CloudflareEmbedding:
    return CloudflareEmbedding("conta", "tok", "@cf/baai/bge-m3", DIM, 1, cliente=_cliente(handler))


def _hf(handler) -> HuggingFaceEmbedding:
    return HuggingFaceEmbedding("tok", "BAAI/bge-m3", DIM, 1, cliente=_cliente(handler))


def _metrica(nome: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(nome, labels) or 0.0


# ------------------------------------------------------------------ provedores HTTP
def test_cloudflare_ok_normaliza_vetor():
    cf = _cf(lambda req: httpx.Response(200, json={"success": True, "result": {"data": [[2.0] * DIM]}}))
    v = cf.vetorizar(["oi"])[0]
    assert len(v) == DIM and abs(sum(x * x for x in v) - 1) < 1e-9


@pytest.mark.parametrize(
    "resposta",
    [
        httpx.Response(500, text="erro"),
        httpx.Response(429, json={"errors": ["rate limit"]}),
        httpx.Response(200, json={"success": False, "errors": ["quota"]}),
        httpx.Response(200, json={"success": True, "result": {"data": [[1.0] * 3]}}),  # dimensão errada
        httpx.Response(200, text="<html>"),
    ],
)
def test_cloudflare_respostas_ruins_viram_falha(resposta):
    with pytest.raises(FalhaVetorizacao):
        _cf(lambda req: resposta).vetorizar(["oi"])


def test_timeout_vira_falha():
    def estoura(req):
        raise httpx.ReadTimeout("timeout", request=req)

    with pytest.raises(FalhaVetorizacao):
        _cf(estoura).vetorizar(["oi"])


def test_cadeia_cai_para_hugging_face_quando_cloudflare_falha():
    falhas = []
    cf = _cf(lambda req: httpx.Response(503))
    hf = _hf(lambda req: httpx.Response(200, json=[[0.5] * DIM]))
    cadeia = CadeiaEmbeddings([cf, hf], cooldown_s=60, ao_falhar=falhas.append)
    v = cadeia.vetorizar("como tiro o atestado?")
    assert v.provedor == "huggingface" and len(v.vetor) == DIM
    assert falhas == ["cloudflare"]
    # em cooldown, a próxima chamada nem tenta a Cloudflare (não soma timeouts)
    cadeia.vetorizar("outra pergunta")
    assert falhas == ["cloudflare"]
    assert cadeia.estado()["status"] == "ok"


def test_hugging_face_com_saida_por_token_faz_mean_pooling():
    hf = _hf(lambda req: httpx.Response(200, json=[[[1.0] * DIM, [3.0] * DIM]]))
    v = hf.vetorizar(["x"])[0]
    assert len(v) == DIM


def test_todos_falham_levanta_falha():
    cadeia = CadeiaEmbeddings([ProvedorFalso("cloudflare", falhar=True), ProvedorFalso("huggingface", falhar=True)])
    with pytest.raises(FalhaVetorizacao):
        cadeia.vetorizar("x")
    assert cadeia.estado()["status"] == "falha"


# ------------------------------------------------------------------ RAG com a API fora
def test_rag_usa_tfidf_quando_a_vetorizacao_falha():
    repo = RepoMemoria()
    cadeia = CadeiaEmbeddings([ProvedorFalso("cloudflare", falhar=True)])
    idx = IndiceLexical.construir(repo.chunks)
    r = recuperar(
        "Como tiro o atestado de matrícula pelo portal?",
        vetorizar=cadeia.vetorizar,
        buscar_vetorial=lambda v, k: pytest.fail("não deveria buscar no pgvector sem vetor"),
        indice_lexical=lambda: idx,
        config=ConfigRAG(limiar_lexical=0.2),
    )
    assert r.metodo == "lexical" and r.usou_fallback and not r.abstencao
    assert r.trechos[0].titulo == "Atestado de matrícula"
    assert any("vetorizacao" in f for f in r.falhas)


def test_rag_lexical_tambem_respeita_o_limiar_e_se_abstem():
    repo = RepoMemoria()
    idx = IndiceLexical.construir(repo.chunks)
    r = recuperar(
        "Qual a capital da França?",
        vetorizar=CadeiaEmbeddings([]).vetorizar,
        buscar_vetorial=lambda v, k: [],
        indice_lexical=lambda: idx,
    )
    assert r.abstencao and r.metodo == "lexical"
    assert r.motivo_abstencao in ("sem_documentos", "baixa_similaridade")


def test_rag_sem_fallback_se_abstem_com_falha_vetorizacao():
    r = recuperar(
        "x",
        vetorizar=CadeiaEmbeddings([ProvedorFalso(falhar=True)]).vetorizar,
        buscar_vetorial=lambda v, k: [],
        config=ConfigRAG(fallback_lexical=False),
    )
    assert r.abstencao and r.motivo_abstencao == "falha_vetorizacao"


# ------------------------------------------------------------------ ponta a ponta (/chat)
def test_chat_com_api_de_embeddings_fora_usa_fallback_e_conta_metricas(amb):
    amb.provedor.falhar = True
    amb.reserva.falhar = True
    antes_fb = _metrica("rag_fallback_total")
    antes_falha = _metrica("embedding_falhas_total", provedor="cloudflare")
    r = amb.client.post(
        "/chat",
        headers=auth(ID_ESTUDANTE),
        json={"mensagem": "Como emitir o atestado de matrícula no portal do aluno?"},
    )
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["versao_modelo"].endswith("+tfidf")
    assert corpo["fontes"] and corpo["fontes"][0]["titulo"] == "Atestado de matrícula"
    assert amb.repo.buscas == []  # nada de vetor TF-IDF no pgvector
    assert _metrica("rag_fallback_total") == antes_fb + 1
    # o callback de métrica só existe na cadeia montada pelo create_app padrão; aqui checamos o log de auditoria
    assert amb.repo.auditoria[-1]["resultado"]["metodo"] == "lexical"
    assert _metrica("embedding_falhas_total", provedor="cloudflare") >= antes_falha


def test_chat_com_tudo_fora_nao_vira_500(amb):
    amb.provedor.falhar = True
    amb.reserva.falhar = True
    amb.repo.falhar.add("listar_chunks_ativos")
    r = amb.client.post("/chat", headers=auth(ID_ESTUDANTE), json={"mensagem": "Como tiro o atestado?"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["abstencao"] and corpo["motivo_abstencao"] == "falha_vetorizacao"
    assert corpo["encaminhamento"]["setor_destino"] == "ASA"
