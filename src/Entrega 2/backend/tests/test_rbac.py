"""Autenticação e menor privilégio por rota (x-papeis do contrato)."""

from __future__ import annotations

import pytest

from tests.contrato import validar
from tests.fakes import (
    EST_RISCO,
    ID_ADMIN,
    ID_ATENDENTE,
    ID_ESTUDANTE,
    ID_TECNICO,
    auth,
    token,
)

UUID_QUALQUER = "11111111-1111-4111-8111-111111111111"
# (método, caminho, corpo)
ROTAS = {
    "chat": ("POST", "/chat", {"mensagem": "Como tiro o atestado?"}),
    "conversas": ("GET", "/chat/conversas", None),
    "feedback": ("POST", "/chat/feedback", {"resposta_id": UUID_QUALQUER, "avaliacao": "util"}),
    "casos": ("GET", "/casos", None),
    "caso": ("GET", f"/casos/{EST_RISCO}", None),
    "historico": ("GET", f"/casos/{EST_RISCO}/historico", None),
    "validacao": (
        "POST",
        f"/casos/{EST_RISCO}/validacao",
        {"score_id": UUID_QUALQUER, "decisao": "confirmado", "justificativa": "x" * 25},
    ),
    "inferir": ("POST", "/risco/inferir", {"estudante_id": EST_RISCO}),
    "modelo": ("GET", "/risco/modelo", None),
    "dashboard": ("GET", "/admin/dashboard", None),
    "documentos": ("GET", "/admin/documentos", None),
}
PERMITIDAS = {
    ID_ESTUDANTE: {"chat", "conversas", "feedback"},
    ID_ATENDENTE: {"casos", "caso", "historico", "validacao", "modelo"},
    ID_ADMIN: {"casos", "caso", "historico", "validacao", "inferir", "modelo", "dashboard", "documentos"},
    ID_TECNICO: {"inferir", "modelo"},
}


def _chamar(client, rota: str, headers: dict[str, str]):
    metodo, caminho, corpo = ROTAS[rota]
    return client.request(metodo, caminho, json=corpo, headers=headers)


@pytest.mark.parametrize("rota", sorted(ROTAS))
def test_sem_token_responde_401_no_formato_do_contrato(amb, rota):
    r = _chamar(amb.client, rota, {})
    assert r.status_code == 401
    validar("Erro", r.json())
    assert r.json()["codigo"] == "nao_autenticado"
    assert r.headers["X-Request-ID"] == r.json()["request_id"]


@pytest.mark.parametrize("uid", sorted(PERMITIDAS))
@pytest.mark.parametrize("rota", sorted(ROTAS))
def test_matriz_de_papeis(amb, uid, rota):
    r = _chamar(amb.client, rota, auth(uid))
    if rota in PERMITIDAS[uid]:
        assert r.status_code not in (401, 403), r.json()
        assert r.status_code < 500, r.json()
    else:
        assert r.status_code == 403, (uid, rota, r.status_code)
        assert r.json()["codigo"] == "sem_permissao"


@pytest.mark.parametrize(
    "caminho",
    [
        "/casos",
        f"/casos/{EST_RISCO}",
        f"/casos/{EST_RISCO}/historico",
        "/admin/dashboard",
        "/admin/documentos",
        "/risco/modelo",
    ],
)
def test_estudante_nunca_acessa_casos_risco_ou_admin(amb, caminho):
    r = amb.client.get(caminho, headers=auth(ID_ESTUDANTE))
    assert r.status_code == 403
    # e nada sobre risco vaza no corpo do erro
    assert "score" not in r.text.lower()


def test_estudante_nao_valida_caso_nem_infere(amb):
    r = amb.client.post(
        f"/casos/{EST_RISCO}/validacao",
        headers=auth(ID_ESTUDANTE),
        json={"score_id": UUID_QUALQUER, "decisao": "rejeitado", "justificativa": "x" * 30},
    )
    assert r.status_code == 403
    assert amb.repo.validacoes == []
    r = amb.client.post("/risco/inferir", headers=auth(ID_ESTUDANTE), json={"estudante_id": EST_RISCO})
    assert r.status_code == 403


def test_token_expirado_assinatura_invalida_e_audiencia_errada(amb):
    for t in (
        token(ID_ADMIN, exp_em=-10),
        token(ID_ADMIN, segredo="outro-segredo-qualquer-bem-longo-123456"),
        token(ID_ADMIN, aud="anon"),
        "nao.e.jwt",
    ):
        r = amb.client.get("/me", headers={"Authorization": f"Bearer {t}"})
        assert r.status_code == 401, t
        assert r.json()["codigo"] == "nao_autenticado"


def test_usuario_sem_perfil_ou_inativo_recebe_403(amb):
    r = amb.client.get("/me", headers=auth("99999999-9999-4999-8999-999999999999"))
    assert r.status_code == 403
    amb.repo.perfis[ID_ATENDENTE]["ativo"] = False
    r = amb.client.get("/casos", headers=auth(ID_ATENDENTE))
    assert r.status_code == 403


def test_papel_vem_do_banco_e_nao_do_token(amb):
    # Um token "forjado" com role=administrador não muda nada: vale o papel em perfis
    import time

    import jwt

    from tests.fakes import SEGREDO_JWT

    t = jwt.encode(
        {
            "sub": ID_ESTUDANTE,
            "aud": "authenticated",
            "exp": int(time.time()) + 60,
            "role": "administrador",
            "user_role": "administrador",
        },
        SEGREDO_JWT,
        algorithm="HS256",
    )
    r = amb.client.get("/admin/dashboard", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 403


def test_me_por_papel(amb):
    r = amb.client.get("/me", headers=auth(ID_ESTUDANTE))
    assert r.status_code == 200
    validar("Me", r.json())
    assert r.json()["papel"] == "estudante" and r.json()["estudante"]["ra"] == "99999901"
    r = amb.client.get("/me", headers=auth(ID_ATENDENTE))
    validar("Me", r.json())
    assert r.json()["estudante"] is None
