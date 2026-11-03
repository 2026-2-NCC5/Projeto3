"""Auditoria (regra 6): usuário, data/hora, versão, entrada, resultado, decisão."""

from __future__ import annotations

import logging
from typing import Any

from app.core.auth import Usuario
from app.core.contexto import request_id_atual
from app.db.repositorio import ErroRepositorio, Repositorio

log = logging.getLogger("asa.auditoria")


def auditar(
    repo: Repositorio,
    usuario: Usuario | None,
    acao: str,
    entidade: str,
    entidade_id: str | None = None,
    *,
    entrada: dict[str, Any] | None = None,
    resultado: dict[str, Any] | None = None,
    versao: str | None = None,
) -> None:
    """Grava em auditoria_logs. Falha de gravação não derruba a operação já
    concluída, mas fica registrada no log como ERROR (alerta operacional)."""
    registro = {
        "usuario_id": usuario.id if usuario else None,
        "papel": usuario.papel.value if usuario else None,
        "acao": acao,
        "entidade": entidade,
        "entidade_id": entidade_id,
        "request_id": request_id_atual(),
        "versao": versao,
        "entrada": entrada,
        "resultado": resultado,
        "detalhes": None,
    }
    try:
        repo.registrar_auditoria(registro)
    except ErroRepositorio:
        log.error("falha ao gravar auditoria", extra={"acao": acao, "entidade": entidade, "entidade_id": entidade_id})
