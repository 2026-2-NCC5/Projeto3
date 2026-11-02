"""Acesso aos serviços guardados em app.state (montados no lifespan)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query, Request

from app.services.casos import ServicoCasos
from app.services.chat import ServicoChat
from app.services.documentos import ServicoDocumentos
from app.services.risco import ServicoRisco


def _chat(request: Request) -> ServicoChat:
    return request.app.state.servico_chat


def _casos(request: Request) -> ServicoCasos:
    return request.app.state.servico_casos


def _risco(request: Request) -> ServicoRisco:
    return request.app.state.servico_risco


def _documentos(request: Request) -> ServicoDocumentos:
    return request.app.state.servico_documentos


Chat = Annotated[ServicoChat, Depends(_chat)]
Casos = Annotated[ServicoCasos, Depends(_casos)]
Risco = Annotated[ServicoRisco, Depends(_risco)]
Documentos = Annotated[ServicoDocumentos, Depends(_documentos)]

Pagina = Annotated[int, Query(ge=1)]
PorPagina = Annotated[int, Query(ge=1, le=100)]
