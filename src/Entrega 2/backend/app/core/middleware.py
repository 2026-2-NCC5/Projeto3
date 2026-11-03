"""Middleware ASGI: request_id, log de acesso em JSON, métricas e rede de segurança.

É ASGI puro (não BaseHTTPMiddleware) para garantir o header X-Request-ID
inclusive nas respostas de erro 500 geradas aqui.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core import metricas
from app.core.contexto import papel_var, request_id_var, usuario_id_var
from app.core.erros import corpo_erro

log = logging.getLogger("asa.acesso")
_ID_VALIDO = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_ROTAS_SILENCIOSAS = {"/health", "/metrics"}


def _rota_template(scope: Scope) -> str:
    rota = scope.get("route")
    caminho = getattr(rota, "path", None)
    return caminho or "nao_mapeada"


class MiddlewareRequisicao:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        enviado = headers.get("x-request-id", "")
        request_id = enviado if _ID_VALIDO.match(enviado) else str(uuid.uuid4())
        tokens = (
            request_id_var.set(request_id),
            usuario_id_var.set(None),
            papel_var.set(None),
        )
        inicio = time.perf_counter()
        status = 500
        resposta_iniciada = False

        async def enviar(msg: Message) -> None:
            nonlocal status, resposta_iniciada
            if msg["type"] == "http.response.start":
                status = msg["status"]
                resposta_iniciada = True
                msg.setdefault("headers", [])
                msg["headers"] = [h for h in msg["headers"] if h[0].lower() != b"x-request-id"]
                msg["headers"].append((b"x-request-id", request_id.encode()))
            await send(msg)

        try:
            await self.app(scope, receive, enviar)
        except Exception:
            log.exception("erro não tratado")
            if not resposta_iniciada:
                corpo = json.dumps(
                    corpo_erro("erro_interno", "Algo deu errado do nosso lado. Tente de novo em instantes."),
                    ensure_ascii=False,
                ).encode()
                await enviar(
                    {
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(corpo)).encode()),
                        ],
                    }
                )
                await enviar({"type": "http.response.body", "body": corpo})
        finally:
            latencia = time.perf_counter() - inicio
            rota = _rota_template(scope)
            metodo = scope.get("method", "-")
            metricas.http_requests_total.labels(rota, metodo, str(status)).inc()
            metricas.http_request_duration_seconds.labels(rota, metodo).observe(latencia)
            if status >= 400:
                metricas.http_erros_total.labels(rota, str(status)).inc()
            if scope.get("path") not in _ROTAS_SILENCIOSAS or status >= 400:
                nivel = logging.ERROR if status >= 500 else logging.WARNING if status >= 400 else logging.INFO
                log.log(
                    nivel,
                    "requisicao",
                    extra={
                        "rota": rota,
                        "caminho": scope.get("path"),
                        "metodo": metodo,
                        "status": status,
                        "latencia_ms": round(latencia * 1000, 1),
                    },
                )
            for var, tok in zip((request_id_var, usuario_id_var, papel_var), tokens, strict=True):
                var.reset(tok)
