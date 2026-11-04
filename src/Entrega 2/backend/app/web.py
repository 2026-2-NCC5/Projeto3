"""Container único: o mesmo processo serve a API e o build do web (PWA).

Mesmo roteamento do Caddy (infra/caddy/Caddyfile), para o front funcionar igual:
- /api/*            -> API (root_path=/api: a API enxerga /chat, /casos...)
- /health, /metrics -> API (healthcheck do Render/Fly/Cloud Run)
- arquivo existente -> o arquivo (assets/ com cache longo)
- qualquer outra    -> index.html (rotas do SPA: /chat, /fila, /admin...)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from starlette.responses import FileResponse, PlainTextResponse
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

ROTAS_DA_API_NA_RAIZ = {"/health", "/metrics"}
SEM_CACHE = {"/", "/index.html", "/sw.js", "/manifest.webmanifest"}


def _cabecalhos_seguranca(connect_extra: str) -> list[tuple[bytes, bytes]]:
    csp = (
        "default-src 'self'; script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; "
        f"img-src 'self' data:; connect-src 'self' {connect_extra}; manifest-src 'self'; worker-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    return [
        (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
        (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
        (b"cross-origin-opener-policy", b"same-origin"),
        (b"content-security-policy", csp.strip().encode()),
    ]


class AppComWeb:
    def __init__(self, api: ASGIApp, dist: Path, connect_extra: str = "") -> None:
        self.api = api
        self.dist = dist.resolve()
        self.index = self.dist / "index.html"
        self.arquivos = StaticFiles(directory=str(self.dist), check_dir=True)
        self.cabecalhos = _cabecalhos_seguranca(connect_extra)

    def _arquivo_existe(self, caminho: str) -> bool:
        alvo = (self.dist / caminho.lstrip("/")).resolve()
        return alvo.is_file() and self.dist in alvo.parents

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":  # lifespan (warm-up) e websockets vão para a API
            await self.api(scope, receive, send)
            return
        caminho: str = scope["path"]
        if caminho == "/api" or caminho.startswith("/api/"):
            await self.api({**scope, "root_path": scope.get("root_path", "") + "/api"}, receive, send)
            return
        if caminho in ROTAS_DA_API_NA_RAIZ:
            await self.api(scope, receive, send)
            return
        await self._web(scope, receive, send)

    async def _web(self, scope: Scope, receive: Receive, send: Send) -> None:
        caminho: str = scope["path"]
        if scope["method"] not in ("GET", "HEAD"):
            await PlainTextResponse("Método não permitido", status_code=405)(scope, receive, send)
            return
        cache = (
            b"public, max-age=31536000, immutable"
            if caminho.startswith("/assets/")
            else b"no-cache"
            if caminho in SEM_CACHE or not self._arquivo_existe(caminho)
            else b"public, max-age=3600"
        )

        async def enviar(msg: Message) -> None:
            if msg["type"] == "http.response.start":
                msg["headers"] = [*msg.get("headers", []), *self.cabecalhos, (b"cache-control", cache)]
            await send(msg)

        if caminho != "/" and self._arquivo_existe(caminho):
            await self.arquivos(scope, receive, enviar)
        else:
            await FileResponse(self.index, media_type="text/html")(scope, receive, enviar)


def com_web(api: Any, dist: Path) -> AppComWeb:
    st = api.state.settings
    extra = ""
    if st.supabase_url and not st.demo_mode:
        u = urlsplit(st.supabase_url)
        extra = f"{u.scheme}://{u.netloc} wss://{u.netloc}"
    return AppComWeb(api, dist, extra)
