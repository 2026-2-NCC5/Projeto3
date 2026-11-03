"""Modelo de risco: inferência (admin, equipe técnica) e metadados (equipe ASA + técnica)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import Risco
from app.core.auth import LeituraModelo, OperacaoModelo
from app.schemas import InferenciaEntrada, InferenciaResultado, ModeloInfo

router = APIRouter(prefix="/risco", tags=["Risco"])


@router.post("/inferir", response_model=InferenciaResultado)
def inferir_risco(corpo: InferenciaEntrada, usuario: OperacaoModelo, risco: Risco) -> dict:
    return risco.inferir(usuario, corpo)


@router.get("/modelo", response_model=ModeloInfo)
def modelo_risco(usuario: LeituraModelo, risco: Risco) -> dict:
    return risco.info()
