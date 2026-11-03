"""/health, /metrics, X-Request-ID, logs JSON e formato de erro."""

from __future__ import annotations

import json
import logging

from tests.contrato import validar
from tests.fakes import ID_ESTUDANTE, auth


def test_health_ok(amb):
    r = amb.client.get("/health")
    assert r.status_code == 200
    corpo = r.json()
    validar("Saude", corpo)
    assert corpo["status"] == "ok" and corpo["dependencias"]["banco"]["status"] == "ok"
    assert corpo["versao_modelo_risco"].startswith("rl-placeholder")


def test_health_degradado_sem_embeddings_e_503_sem_banco(amb):
    amb.provedor.falhar = amb.reserva.falhar = True
    amb.app.state.embeddings._cooldown = 60
    try:
        amb.app.state.embeddings.vetorizar("x")
    except Exception:  # noqa: BLE001
        pass
    corpo = amb.client.get("/health").json()
    assert corpo["status"] == "degradado" and corpo["dependencias"]["embeddings"]["status"] == "falha"
    amb.repo.falhar.add("ping")
    r = amb.client.get("/health")
    assert r.status_code == 503 and r.json()["codigo"] == "indisponivel"


def test_metrics_prometheus(amb):
    amb.client.post("/chat", headers=auth(ID_ESTUDANTE), json={"mensagem": "Posso levar meu cachorro?"})
    r = amb.client.get("/metrics")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    texto = r.text
    for nome in (
        "http_requests_total",
        "http_request_duration_seconds_bucket",
        "chat_respostas_total",
        "chat_abstencoes_total",
        "rag_fallback_total",
        "embedding_falhas_total",
        "risco_inferencias_total",
        "validacoes_total",
        "chat_feedback_total",
        "http_erros_total",
    ):
        assert nome in texto, nome
    assert 'rota="/chat"' in texto  # rota pelo template, não pelo caminho real


def test_request_id_propagado_ou_gerado(amb):
    r = amb.client.get("/health", headers={"X-Request-ID": "meu-id-123"})
    assert r.headers["X-Request-ID"] == "meu-id-123"
    r = amb.client.get("/health", headers={"X-Request-ID": "invalido com espaco"})
    assert r.headers["X-Request-ID"] != "invalido com espaco" and len(r.headers["X-Request-ID"]) == 36
    r = amb.client.get("/rota-que-nao-existe")
    assert r.status_code == 404 and r.json()["request_id"] == r.headers["X-Request-ID"]


def test_erro_inesperado_vira_500_no_formato_do_contrato(amb):
    amb.app.state.servico_casos.listar = lambda *a, **k: 1 / 0
    from tests.fakes import ID_ATENDENTE

    r = amb.client.get("/casos", headers=auth(ID_ATENDENTE))
    assert r.status_code == 500
    validar("Erro", r.json())
    assert r.json()["codigo"] == "erro_interno" and "ZeroDivision" not in r.text
    assert r.headers["X-Request-ID"] == r.json()["request_id"]


def test_cors_configuravel(amb):
    r = amb.client.options(
        "/chat",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
    r = amb.client.options(
        "/chat", headers={"Origin": "https://malicioso.example", "Access-Control-Request-Method": "POST"}
    )
    assert "access-control-allow-origin" not in r.headers


def test_log_de_acesso_em_json_com_usuario_e_latencia(amb, caplog):
    from app.core.logs import FormatadorJSON

    caplog.set_level(logging.INFO)
    amb.client.get("/me", headers=auth(ID_ESTUDANTE))
    linhas = [json.loads(FormatadorJSON().format(r)) for r in caplog.records]
    acesso = [linha for linha in linhas if linha.get("msg") == "requisicao" and linha.get("rota") == "/me"]
    assert acesso, linhas
    log = acesso[-1]
    assert log["status"] == 200 and log["usuario_id"] == ID_ESTUDANTE and log["papel"] == "estudante"
    assert log["request_id"] and log["latencia_ms"] >= 0 and log["nivel"] == "INFO"
    assert "Bearer" not in json.dumps(linhas)  # token nunca vai para o log
