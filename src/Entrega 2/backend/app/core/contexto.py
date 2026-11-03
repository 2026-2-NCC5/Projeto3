"""Contexto da requisição (request_id, usuário) para logs e auditoria."""

from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
usuario_id_var: ContextVar[str | None] = ContextVar("usuario_id", default=None)
papel_var: ContextVar[str | None] = ContextVar("papel", default=None)


def request_id_atual() -> str:
    return request_id_var.get() or "-"
