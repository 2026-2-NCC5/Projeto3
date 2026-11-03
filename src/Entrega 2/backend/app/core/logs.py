"""Logs estruturados em JSON (uma linha por evento).

Campos fixos: ts, nivel, logger, msg, request_id, usuario_id, papel.
Campos extras passados em `extra={...}` entram no JSON (rota, status, latencia_ms...).
Nunca logar token, chave ou texto livre do estudante.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

from app.core.contexto import papel_var, request_id_var, usuario_id_var

_CAMPOS_PADRAO = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime", "color_message"}
_CAMPOS_CONTEXTO = ("request_id", "usuario_id", "papel")
_fabrica_original = logging.getLogRecordFactory()


def _fabrica_com_contexto(*args: object, **kwargs: object) -> logging.LogRecord:
    """Anexa request_id/usuário ao registro NO MOMENTO em que ele é criado
    (vale mesmo se a formatação acontecer depois, fora da requisição)."""
    record = _fabrica_original(*args, **kwargs)
    record.request_id = request_id_var.get()
    record.usuario_id = usuario_id_var.get()
    record.papel = papel_var.get()
    return record


class FormatadorJSON(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        dados: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "nivel": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for campo in _CAMPOS_CONTEXTO:
            dados[campo] = getattr(record, campo, None)
        for chave, valor in vars(record).items():
            if chave not in _CAMPOS_PADRAO and chave not in _CAMPOS_CONTEXTO and not chave.startswith("_"):
                dados[chave] = valor
        if record.exc_info:
            dados["erro"] = self.formatException(record.exc_info)
        return json.dumps(dados, ensure_ascii=False, default=str)


def configurar_logs(nivel: str = "INFO") -> None:
    logging.setLogRecordFactory(_fabrica_com_contexto)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(FormatadorJSON())
    raiz = logging.getLogger()
    raiz.handlers[:] = [handler]
    raiz.setLevel(nivel.upper())
    # o uvicorn tem o próprio log de acesso; usamos o nosso (com request_id)
    for nome in ("uvicorn", "uvicorn.error"):
        logging.getLogger(nome).handlers[:] = []
        logging.getLogger(nome).propagate = True
    logging.getLogger("uvicorn.access").disabled = True
    for ruidoso in ("httpx", "httpcore", "hpack"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)
