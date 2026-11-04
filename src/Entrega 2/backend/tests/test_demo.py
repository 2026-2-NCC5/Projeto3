"""Modo de demonstração (DEMO_MODE=true) e container único (API + web)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.web import AppComWeb
from tests.conftest import settings_teste


@pytest.fixture(scope="module")
def demo(modelo: object) -> Iterator[TestClient]:
    app = create_app(settings_teste(demo_mode=True, supabase_jwt_secret=""), modelo=modelo)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def _entrar(c: TestClient, papel: str) -> dict[str, str]:
    r = c.post("/demo/entrar", json={"papel": papel})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_estado_e_login_por_papel(demo: TestClient) -> None:
    assert demo.get("/demo/estado").json()["demo"] is True
    for papel in ("estudante", "atendente", "administrador"):
        me = demo.get("/me", headers=_entrar(demo, papel)).json()
        assert me["papel"] == papel


def test_login_por_senha(demo: TestClient) -> None:
    ok = demo.post("/demo/entrar", json={"email": "atendente.demo@example.com", "senha": "AsaTurbo#Demo2026"})
    assert ok.status_code == 200
    errado = demo.post("/demo/entrar", json={"email": "atendente.demo@example.com", "senha": "outra"})
    assert errado.status_code == 401


def test_rbac_continua_valendo(demo: TestClient) -> None:
    assert demo.get("/casos", headers=_entrar(demo, "estudante")).status_code == 403
    assert demo.post("/demo/reiniciar", headers=_entrar(demo, "atendente")).status_code == 403


PERGUNTAS_SUGERIDAS = [
    "Como faço para trancar a matrícula?",
    "Como emito o atestado de matrícula?",
    "Como funciona o estágio obrigatório?",
    "Como solicito atividades complementares?",
    "Perdi uma prova, como faço a prova substitutiva?",
]


@pytest.mark.parametrize("pergunta", PERGUNTAS_SUGERIDAS)
def test_perguntas_sugeridas_respondem_com_fonte(demo: TestClient, pergunta: str) -> None:
    r = demo.post("/chat", json={"mensagem": pergunta}, headers=_entrar(demo, "estudante"))
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["abstencao"] is False, corpo
    assert corpo["fontes"] and corpo["fontes"][0]["data_atualizacao"]


def test_continuacao_e_abstencao(demo: TestClient) -> None:
    h = _entrar(demo, "estudante")
    r1 = demo.post("/chat", json={"mensagem": "Como faço para trancar a matrícula?"}, headers=h).json()
    r2 = demo.post("/chat", json={"mensagem": "e o prazo?", "conversa_id": r1["conversa_id"]}, headers=h).json()
    assert r2["abstencao"] is False
    assert "trancamento" in r2["fontes"][0]["titulo"].lower()
    fora = demo.post("/chat", json={"mensagem": "Qual é o cardápio do restaurante hoje?"}, headers=h).json()
    assert fora["abstencao"] is True
    assert fora["encaminhamento"]


def test_fila_abre_com_tres_historias_vermelhas(demo: TestClient) -> None:
    itens = demo.get("/casos", headers=_entrar(demo, "atendente")).json()["itens"]
    topo = itens[:3]
    assert [i["categoria"] for i in topo] == ["vermelho"] * 3
    assert all(i["prioridade"] == "urgente" and i["tendencia"] == "subindo" for i in topo)
    assert itens[3]["prioridade"] != "urgente"


def test_painel_nao_abre_zerado(demo: TestClient) -> None:
    d = demo.get("/admin/dashboard", headers=_entrar(demo, "administrador")).json()
    assert d["chat"]["perguntas"] > 100
    assert 0 < d["chat"]["taxa_abstencao"] < 0.3
    assert d["chat"]["feedback"]["util"] > d["chat"]["feedback"]["nao_util"] > 0
    assert all(d["risco"]["distribuicao"][c] > 0 for c in ("verde", "amarelo", "vermelho"))
    assert d["chat"]["principais_documentos"]


def test_desativar_documento_tira_da_busca_e_reiniciar_volta(demo: TestClient) -> None:
    h = _entrar(demo, "administrador")
    docs = demo.get("/admin/documentos", params={"busca": "trancamento", "ativo": True}, headers=h).json()["itens"]
    assert docs
    for d in docs:
        r = demo.post(f"/admin/documentos/{d['id']}/desativar", json={"motivo": "Teste da demonstração"}, headers=h)
        assert r.status_code in (200, 204), r.text
    resp = demo.post(
        "/chat", json={"mensagem": "Como faço para trancar a matrícula?"}, headers=_entrar(demo, "estudante")
    ).json()
    assert all("trancamento" not in f["titulo"].lower() for f in resp["fontes"] if not resp["abstencao"])

    assert demo.post("/demo/reiniciar", headers=h).status_code == 200
    depois = demo.post(
        "/chat", json={"mensagem": "Como faço para trancar a matrícula?"}, headers=_entrar(demo, "estudante")
    ).json()
    assert depois["abstencao"] is False


def test_rotas_de_demo_nao_existem_fora_do_modo_demo(amb: object) -> None:
    assert amb.client.post("/demo/entrar", json={"papel": "administrador"}).status_code == 404  # type: ignore[attr-defined]


def test_container_unico_serve_api_e_spa(tmp_path: Path, modelo: object) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>ASA Turbo</title>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    api = create_app(settings_teste(demo_mode=True, supabase_jwt_secret=""), modelo=modelo)
    with TestClient(AppComWeb(api, tmp_path)) as c:
        assert c.get("/health").status_code == 200
        assert c.post("/api/demo/entrar", json={"papel": "estudante"}).status_code == 200
        spa = c.get("/fila")
        assert spa.status_code == 200 and "ASA Turbo" in spa.text
        assert "frame-ancestors 'none'" in spa.headers["content-security-policy"]
        assert "immutable" in c.get("/assets/app.js").headers["cache-control"]
        assert c.get("/../../etc/passwd").text.startswith("<!doctype")
