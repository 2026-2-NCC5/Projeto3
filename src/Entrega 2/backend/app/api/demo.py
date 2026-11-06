"""Rotas do modo de demonstração. Só existem com DEMO_MODE=true.

O backend emite o próprio JWT (HS256) para os 3 perfis de demonstração, no
mesmo formato do Supabase Auth. O resto da API (RBAC, auditoria) é idêntico.
Não fazem parte de docs/api-contract.yaml: são um atalho de apresentação.
"""

from __future__ import annotations

import hmac
import time
from typing import Literal

import jwt
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.core.auth import Papel, SoAdmin, Usuario
from app.core.erros import ErroAPI
from app.services.aquecimento import aquecer
from app.services.auditoria import auditar

router = APIRouter(prefix="/demo", tags=["Demonstração"])

PERFIS_DEMO = {
    "estudante": "estudante.demo@example.com",
    "atendente": "atendente.demo@example.com",
    "administrador": "admin.demo@example.com",
}
DURACAO_S = 8 * 3600


class EntradaDemo(BaseModel):
    papel: Literal["estudante", "atendente", "administrador"] | None = None
    email: str | None = Field(default=None, max_length=200)
    senha: str | None = Field(default=None, max_length=200)


@router.get("/estado")
def estado(request: Request) -> dict[str, object]:
    repo = request.app.state.repo
    por_email = {p["email"]: p for p in repo.perfis.values()}
    return {
        "demo": True,
        "perfis": [
            {"papel": papel, "email": email, "nome": por_email.get(email, {}).get("nome_completo", "")}
            for papel, email in PERFIS_DEMO.items()
        ],
    }


@router.post("/entrar")
async def entrar(entrada: EntradaDemo, request: Request) -> dict[str, object]:
    st = request.app.state
    if entrada.papel:
        email = PERFIS_DEMO[entrada.papel]
    else:
        email = (entrada.email or "").strip().lower()
        senha_ok = hmac.compare_digest(
            (entrada.senha or "").encode(), st.settings.demo_password.get_secret_value().encode()
        )
        if email not in PERFIS_DEMO.values() or not senha_ok:
            raise ErroAPI("nao_autenticado", "E-mail ou senha não conferem. Confira e tente de novo.")
    perfil = next((p for p in st.repo.perfis.values() if p["email"] == email), None)
    if not perfil:
        raise ErroAPI("nao_autenticado", "Perfil de demonstração não encontrado.")
    agora = int(time.time())
    token = jwt.encode(
        {
            "sub": perfil["id"],
            "aud": st.settings.jwt_audience,
            "iat": agora,
            "exp": agora + DURACAO_S,
            "email": email,
            "role": "authenticated",
        },
        st.settings.supabase_jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    usuario = Usuario(id=perfil["id"], email=email, nome=perfil["nome_completo"], papel=Papel(perfil["papel"]))
    await run_in_threadpool(
        auditar, st.repo, usuario, "login_demo", "perfis", perfil["id"], entrada={"papel": perfil["papel"]}
    )
    return {"access_token": token, "token_type": "bearer", "expires_in": DURACAO_S}


@router.post("/reiniciar")
async def reiniciar(_admin: SoAdmin, request: Request) -> dict[str, object]:
    """Volta os dados da demo ao estado inicial (conversas, validações, documentos)."""
    st = request.app.state
    await run_in_threadpool(st.repo.reiniciar)
    st.indice_lexical.invalidar()
    st.cache_perfis.limpar()
    await run_in_threadpool(aquecer, st)
    return {"ok": True, "historias": st.repo.historias}
