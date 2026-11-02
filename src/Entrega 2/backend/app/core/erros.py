"""Erros no formato do contrato: {codigo, mensagem, request_id, detalhes?}."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.contexto import request_id_atual

log = logging.getLogger("asa.erros")

MENSAGENS = {
    "requisicao_invalida": "Requisição inválida.",
    "nao_autenticado": "Sua sessão expirou. Entre novamente.",
    "sem_permissao": "Seu perfil não tem acesso a esta área.",
    "nao_encontrado": "Não encontramos esse registro.",
    "conflito": "O registro mudou desde a última leitura. Recarregue para ver a versão nova.",
    "validacao": "Revise os campos destacados.",
    "limite_excedido": "Muitas mensagens em pouco tempo. Aguarde alguns segundos.",
    "erro_interno": "Algo deu errado do nosso lado. Tente de novo em instantes.",
    "indisponivel": "Serviço temporariamente indisponível. Tente de novo em instantes.",
}

STATUS = {
    "requisicao_invalida": 400,
    "nao_autenticado": 401,
    "sem_permissao": 403,
    "nao_encontrado": 404,
    "conflito": 409,
    "validacao": 422,
    "limite_excedido": 429,
    "erro_interno": 500,
    "indisponivel": 503,
}


class ErroAPI(Exception):
    def __init__(
        self,
        codigo: str,
        mensagem: str | None = None,
        *,
        detalhes: list[dict[str, str]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.codigo = codigo
        self.status = STATUS[codigo]
        self.mensagem = mensagem or MENSAGENS[codigo]
        self.detalhes = detalhes
        self.headers = headers or {}
        super().__init__(self.mensagem)


def NaoEncontrado(msg: str | None = None) -> ErroAPI:  # noqa: N802 - fábrica com cara de exceção
    return ErroAPI("nao_encontrado", msg)


def Conflito(msg: str | None = None) -> ErroAPI:  # noqa: N802
    return ErroAPI("conflito", msg)


def Indisponivel(msg: str | None = None) -> ErroAPI:  # noqa: N802
    return ErroAPI("indisponivel", msg)


def corpo_erro(codigo: str, mensagem: str, detalhes: list[dict[str, str]] | None = None) -> dict[str, Any]:
    corpo: dict[str, Any] = {"codigo": codigo, "mensagem": mensagem, "request_id": request_id_atual()}
    if detalhes:
        corpo["detalhes"] = detalhes
    return corpo


def resposta_erro(
    codigo: str,
    mensagem: str | None = None,
    detalhes: list[dict[str, str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=STATUS[codigo],
        content=corpo_erro(codigo, mensagem or MENSAGENS[codigo], detalhes),
        headers=headers,
    )


_TRADUCOES = {
    "missing": "Campo obrigatório.",
    "string_too_short": "Texto curto demais (mínimo {min_length} caracteres).",
    "string_too_long": "Texto longo demais (máximo {max_length} caracteres).",
    "too_long": "Itens demais (máximo {max_length}).",
    "int_parsing": "Deve ser um número inteiro.",
    "float_parsing": "Deve ser um número.",
    "bool_parsing": "Deve ser verdadeiro ou falso.",
    "uuid_parsing": "Identificador inválido.",
    "date_from_datetime_parsing": "Data inválida (use AAAA-MM-DD).",
    "date_parsing": "Data inválida (use AAAA-MM-DD).",
    "datetime_parsing": "Data e hora inválidas (ISO 8601).",
    "datetime_from_date_parsing": "Data e hora inválidas (ISO 8601).",
    "enum": "Valor não permitido.",
    "literal_error": "Valor não permitido.",
    "greater_than_equal": "Deve ser maior ou igual a {ge}.",
    "less_than_equal": "Deve ser menor ou igual a {le}.",
    "extra_forbidden": "Campo não reconhecido.",
}


def _traduzir(erro: dict[str, Any]) -> str:
    modelo = _TRADUCOES.get(erro.get("type", ""))
    if modelo is None:
        msg = str(erro.get("msg", "Valor inválido."))
        return msg.removeprefix("Value error, ")
    try:
        return modelo.format(**(erro.get("ctx") or {}))
    except (KeyError, IndexError):
        return modelo


def _campo(loc: tuple[Any, ...]) -> str:
    partes = [str(p) for p in loc[1:]] if len(loc) > 1 else [str(p) for p in loc]
    return ".".join(partes) or str(loc[0])


def registrar_handlers(app: FastAPI) -> None:
    @app.exception_handler(ErroAPI)
    async def _erro_api(_: Request, exc: ErroAPI) -> JSONResponse:
        return resposta_erro(exc.codigo, exc.mensagem, exc.detalhes, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validacao(_: Request, exc: RequestValidationError) -> JSONResponse:
        erros = list(exc.errors())
        if any(e.get("type") == "json_invalid" for e in erros):
            return resposta_erro("requisicao_invalida", "O corpo da requisição não é um JSON válido.")
        detalhes = [{"campo": _campo(tuple(e.get("loc", ()))), "mensagem": _traduzir(e)} for e in erros]
        # Parâmetro de query/path inválido = 400; corpo com campo inválido = 422 (contrato)
        if all(e.get("loc", ("body",))[0] in ("query", "path", "header") for e in erros):
            primeiro = detalhes[0]
            return resposta_erro(
                "requisicao_invalida",
                f"Parâmetro '{primeiro['campo']}': {primeiro['mensagem']}",
                detalhes,
            )
        return resposta_erro("validacao", None, detalhes)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            return resposta_erro("nao_encontrado", "Rota não encontrada.")
        if exc.status_code == 405:
            return resposta_erro("requisicao_invalida", "Método não permitido nesta rota.")
        if exc.status_code == 401:
            return resposta_erro("nao_autenticado")
        if exc.status_code == 403:
            return resposta_erro("sem_permissao")
        return resposta_erro("requisicao_invalida", str(exc.detail))
