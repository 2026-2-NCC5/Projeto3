"""Autenticação (JWT do Supabase) e autorização por papel (RBAC).

- HS256 com `SUPABASE_JWT_SECRET` (chave legacy) ou, sem ela, as chaves
  públicas do projeto (JWKS em /auth/v1/.well-known/jwks.json).
- O papel NÃO vem do token: é lido em `perfis` (fonte da verdade), com cache curto.
- `exigir_papeis(...)` aplica o menor privilégio rota a rota.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Any

import jwt
from fastapi import Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings
from app.core.contexto import papel_var, usuario_id_var
from app.core.erros import ErroAPI
from app.db.repositorio import ErroRepositorio, Repositorio


class Papel(StrEnum):
    estudante = "estudante"
    atendente = "atendente"
    administrador = "administrador"
    equipe_tecnica = "equipe_tecnica"


@dataclass(frozen=True)
class Usuario:
    id: str
    email: str
    nome: str
    papel: Papel
    estudante: dict[str, Any] | None = None

    @property
    def estudante_id(self) -> str | None:
        return self.estudante["id"] if self.estudante else None


class ValidadorJWT:
    def __init__(self, settings: Settings) -> None:
        self._segredo = settings.supabase_jwt_secret.get_secret_value()
        self._audiencia = settings.jwt_audience
        self._jwks: jwt.PyJWKClient | None = None
        if not self._segredo and settings.supabase_url:
            self._jwks = jwt.PyJWKClient(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json",
                cache_keys=True,
                lifespan=3600,
                timeout=5,
            )

    def validar(self, token: str) -> dict[str, Any]:
        try:
            cabecalho = jwt.get_unverified_header(token)
            alg = cabecalho.get("alg", "")
            if alg == "HS256":
                if not self._segredo:
                    raise ErroAPI("nao_autenticado")
                chave: Any = self._segredo
            elif alg in ("ES256", "RS256") and self._jwks is not None:
                chave = self._jwks.get_signing_key_from_jwt(token).key
            else:
                raise ErroAPI("nao_autenticado")
            dados = jwt.decode(
                token,
                chave,
                algorithms=[alg],
                audience=self._audiencia,
                options={"require": ["exp", "sub"]},
            )
        except ErroAPI:
            raise
        except jwt.ExpiredSignatureError as e:
            raise ErroAPI("nao_autenticado", "Sua sessão expirou. Entre novamente.") from e
        except (jwt.PyJWTError, ValueError) as e:
            raise ErroAPI("nao_autenticado", "Não foi possível validar sua sessão. Entre novamente.") from e
        return dados


class CachePerfis:
    """Cache TTL do perfil (papel) por usuário: evita 1 consulta extra por requisição."""

    def __init__(self, ttl_s: float) -> None:
        self._ttl = ttl_s
        self._dados: dict[str, tuple[float, Usuario]] = {}
        self._trava = threading.Lock()

    def obter(self, uid: str) -> Usuario | None:
        with self._trava:
            item = self._dados.get(uid)
        if item and time.monotonic() - item[0] < self._ttl:
            return item[1]
        return None

    def guardar(self, usuario: Usuario) -> None:
        with self._trava:
            self._dados[usuario.id] = (time.monotonic(), usuario)

    def limpar(self) -> None:
        with self._trava:
            self._dados.clear()


def _carregar_usuario(repo: Repositorio, uid: str) -> Usuario:
    perfil = repo.obter_perfil(uid)
    if not perfil or not perfil.get("ativo", True):
        raise ErroAPI("sem_permissao", "Seu acesso ainda não foi liberado. Procure o ASA.")
    try:
        papel = Papel(perfil["papel"])
    except ValueError as e:
        raise ErroAPI("sem_permissao") from e
    estudante = repo.obter_estudante_por_perfil(uid) if papel is Papel.estudante else None
    return Usuario(
        id=uid, email=perfil.get("email", ""), nome=perfil.get("nome_completo", ""), papel=papel, estudante=estudante
    )


_bearer = HTTPBearer(auto_error=False)


async def usuario_atual(
    request: Request,
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Usuario:
    if credenciais is None or credenciais.scheme.lower() != "bearer" or not credenciais.credentials:
        raise ErroAPI("nao_autenticado", "Entre com seu e-mail e senha para continuar.")
    estado = request.app.state
    dados = await run_in_threadpool(estado.validador_jwt.validar, credenciais.credentials)
    uid = str(dados["sub"])
    usuario = estado.cache_perfis.obter(uid)
    if usuario is None:
        try:
            usuario = await run_in_threadpool(_carregar_usuario, estado.repo, uid)
        except ErroRepositorio as e:
            raise ErroAPI("indisponivel") from e
        estado.cache_perfis.guardar(usuario)
    # async: as contextvars ficam visíveis para o middleware (logs) e a auditoria
    usuario_id_var.set(usuario.id)
    papel_var.set(usuario.papel.value)
    return usuario


def exigir_papeis(*papeis: Papel):  # noqa: ANN201 - devolve uma dependência do FastAPI
    permitidos = frozenset(papeis)

    async def _verificar(usuario: Annotated[Usuario, Depends(usuario_atual)]) -> Usuario:
        if usuario.papel not in permitidos:
            raise ErroAPI("sem_permissao")
        return usuario

    return _verificar


# Atalhos por grupo de rotas (x-papeis do contrato)
QualquerUsuario = Annotated[Usuario, Depends(usuario_atual)]
SoEstudante = Annotated[Usuario, Depends(exigir_papeis(Papel.estudante))]
EquipeASA = Annotated[Usuario, Depends(exigir_papeis(Papel.atendente, Papel.administrador))]
SoAdmin = Annotated[Usuario, Depends(exigir_papeis(Papel.administrador))]
OperacaoModelo = Annotated[Usuario, Depends(exigir_papeis(Papel.administrador, Papel.equipe_tecnica))]
LeituraModelo = Annotated[Usuario, Depends(exigir_papeis(Papel.atendente, Papel.administrador, Papel.equipe_tecnica))]
