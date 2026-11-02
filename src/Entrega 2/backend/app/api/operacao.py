"""/health, /metrics e /me."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response
from fastapi.concurrency import run_in_threadpool

from app.core import metricas
from app.core.auth import QualquerUsuario
from app.core.erros import resposta_erro
from app.db.repositorio import ErroRepositorio
from app.schemas import Me, Saude

router = APIRouter(tags=["Operação"])


@router.get("/health", response_model=Saude)
async def health(request: Request) -> Response | Saude:
    estado = request.app.state
    deps: dict[str, dict[str, object]] = {}
    inicio = time.perf_counter()
    try:
        await run_in_threadpool(estado.repo.ping)
        deps["banco"] = {"status": "ok", "latencia_ms": int((time.perf_counter() - inicio) * 1000)}
    except ErroRepositorio:
        deps["banco"] = {"status": "falha", "latencia_ms": None}
    deps["embeddings"] = estado.embeddings.estado()
    modelo = estado.servico_risco.modelo
    deps["modelo_risco"] = {"status": "ok" if modelo else "falha", "latencia_ms": None}

    if deps["banco"]["status"] == "falha":
        # Sem banco nada funciona: 503 (o orquestrador marca o container como não saudável)
        return resposta_erro("indisponivel", "Banco de dados indisponível.")
    status = "ok" if all(d["status"] == "ok" for d in deps.values()) else "degradado"
    return Saude(
        status=status,
        versao=estado.settings.app_version,
        versao_modelo_risco=modelo.versao if modelo else None,
        dependencias=deps,
        verificado_em=datetime.now(UTC),
    )


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    corpo, tipo = metricas.exportar()
    return Response(content=corpo, media_type=tipo)


@router.get("/me", response_model=Me, tags=["Sessão"])
async def me(usuario: QualquerUsuario) -> Me:
    est = usuario.estudante
    return Me(
        id=usuario.id,
        nome=usuario.nome,
        email=usuario.email,
        papel=usuario.papel.value,
        estudante={"id": est["id"], "ra": est["ra"], "curso": est["curso"], "semestre": est["semestre_atual"]}
        if est
        else None,
    )
