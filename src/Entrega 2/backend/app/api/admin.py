"""Administração: dashboard agregado e base de conhecimento. Acesso: SÓ administrador."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, status

from app.api.deps import Documentos, Pagina, PorPagina
from app.core.auth import SoAdmin
from app.core.erros import ErroAPI
from app.db.repositorio import ErroRepositorio
from app.schemas import (
    Dashboard,
    DesativarEntrada,
    DocumentoDetalhe,
    DocumentoEntrada,
    NovaVersaoEntrada,
    PaginaDocumentos,
)

router = APIRouter(prefix="/admin", tags=["Admin"])
PERIODO_PADRAO = timedelta(days=30)
PERIODO_MAXIMO = timedelta(days=366)


# nulos são omitidos: no contrato esses campos são opcionais mas não anuláveis (ex.: confianca_media)
@router.get("/dashboard", response_model=Dashboard, response_model_exclude_none=True)
def dashboard(
    request: Request,
    usuario: SoAdmin,
    de: Annotated[date | None, Query()] = None,
    ate: Annotated[date | None, Query()] = None,
) -> dict:
    ate = ate or date.today()
    de = de or (ate - PERIODO_PADRAO)
    if de > ate:
        raise ErroAPI("requisicao_invalida", "A data inicial ('de') deve ser anterior à final ('ate').")
    if ate - de > PERIODO_MAXIMO:
        raise ErroAPI("requisicao_invalida", "Escolha um período de até 1 ano.")
    try:
        dados = request.app.state.repo.dashboard(de, ate)
    except ErroRepositorio as e:
        raise ErroAPI("indisponivel") from e
    modelo = request.app.state.servico_risco.modelo
    if not dados["risco"].get("versao_modelo") and modelo:
        dados["risco"]["versao_modelo"] = modelo.versao
    return dados


@router.get("/documentos", response_model=PaginaDocumentos)
def listar_documentos(
    usuario: SoAdmin,
    docs: Documentos,
    busca: Annotated[str | None, Query(max_length=80)] = None,
    categoria: str | None = None,
    ativo: bool | None = None,
    pagina: Pagina = 1,
    por_pagina: PorPagina = 25,
) -> dict:
    return docs.listar(busca, categoria, ativo, pagina, por_pagina)


@router.post("/documentos", response_model=DocumentoDetalhe, status_code=status.HTTP_201_CREATED)
def cadastrar_documento(corpo: DocumentoEntrada, usuario: SoAdmin, docs: Documentos) -> dict:
    return docs.cadastrar(usuario, corpo)


@router.get("/documentos/{documento_id}", response_model=DocumentoDetalhe)
def obter_documento(documento_id: UUID, usuario: SoAdmin, docs: Documentos) -> dict:
    return docs.obter(str(documento_id))


@router.post("/documentos/{documento_id}/versoes", response_model=DocumentoDetalhe, status_code=status.HTTP_201_CREATED)
def nova_versao_documento(documento_id: UUID, corpo: NovaVersaoEntrada, usuario: SoAdmin, docs: Documentos) -> dict:
    return docs.nova_versao(usuario, str(documento_id), corpo)


@router.post("/documentos/{documento_id}/desativar", response_model=DocumentoDetalhe)
def desativar_documento(documento_id: UUID, corpo: DesativarEntrada, usuario: SoAdmin, docs: Documentos) -> dict:
    return docs.desativar(usuario, str(documento_id), corpo.motivo)
