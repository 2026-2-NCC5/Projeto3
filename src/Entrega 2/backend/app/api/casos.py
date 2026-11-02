"""Fila de risco e casos. Acesso: atendente e administrador. Estudante: NUNCA."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import Casos, Pagina, PorPagina
from app.core.auth import EquipeASA
from app.db.repositorio import FiltrosFila
from app.schemas import (
    CasoDetalhe,
    Categoria,
    PaginaCasos,
    PaginaHistorico,
    Prioridade,
    StatusCaso,
    Validacao,
    ValidacaoEntrada,
)

router = APIRouter(prefix="/casos", tags=["Casos"])
Ordenar = Literal["prioridade", "-score", "score", "prazo", "-variacao", "nome"]


@router.get("", response_model=PaginaCasos)
def listar_casos(
    usuario: EquipeASA,
    casos: Casos,
    categoria: Annotated[list[Categoria] | None, Query()] = None,
    prioridade: Annotated[list[Prioridade] | None, Query()] = None,
    status_: Annotated[list[StatusCaso] | None, Query(alias="status")] = None,
    responsavel: Annotated[Literal["eu", "nenhum"] | None, Query()] = None,
    busca: Annotated[str | None, Query(max_length=80)] = None,
    ordenar: Ordenar = "prioridade",
    pagina: Pagina = 1,
    por_pagina: PorPagina = 25,
) -> dict:
    filtros = FiltrosFila(
        categorias=list(categoria or []),
        prioridades=list(prioridade or []),
        status=list(status_ or []),
        responsavel=responsavel,
        busca=busca,
        ordenar=ordenar,
        pagina=pagina,
        por_pagina=por_pagina,
    )
    return casos.listar(usuario, filtros)


@router.get("/{estudante_id}", response_model=CasoDetalhe)
def obter_caso(estudante_id: UUID, usuario: EquipeASA, casos: Casos) -> dict:
    return casos.detalhe(str(estudante_id))


@router.post("/{estudante_id}/validacao", response_model=Validacao, status_code=status.HTTP_201_CREATED)
def validar_caso(estudante_id: UUID, corpo: ValidacaoEntrada, usuario: EquipeASA, casos: Casos) -> dict:
    return casos.validar(usuario, str(estudante_id), corpo)


@router.get("/{estudante_id}/historico", response_model=PaginaHistorico)
def historico_caso(
    estudante_id: UUID, usuario: EquipeASA, casos: Casos, pagina: Pagina = 1, por_pagina: PorPagina = 25
) -> dict:
    return casos.historico(str(estudante_id), pagina, por_pagina)
