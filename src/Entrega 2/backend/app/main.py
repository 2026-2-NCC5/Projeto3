"""Aplicação FastAPI do ASA Turbo.

    uvicorn app.main:app --host 0.0.0.0 --port 8000

`create_app()` aceita dependências injetadas (repositório, embeddings, modelo)
para os testes rodarem sem rede e sem banco.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, casos, chat, operacao, risco
from app.core import metricas
from app.core.auth import CachePerfis, ValidadorJWT
from app.core.config import Settings, get_settings
from app.core.erros import registrar_handlers
from app.core.logs import configurar_logs
from app.core.middleware import MiddlewareRequisicao
from app.db.repositorio import ErroRepositorio, Repositorio
from app.rag.embeddings import CadeiaEmbeddings, CloudflareEmbedding, HuggingFaceEmbedding, Provedor
from app.risk.modelo import RiskModel, carregar_modelo
from app.services.casos import ServicoCasos
from app.services.chat import ServicoChat
from app.services.documentos import ServicoDocumentos
from app.services.indice import CacheIndiceLexical
from app.services.risco import ServicoRisco

log = logging.getLogger("asa.app")
_NAO_CARREGAR = object()


class RepositorioIndisponivel:
    """Usado quando SUPABASE_URL/SUPABASE_SERVICE_KEY não estão configurados:
    a API sobe (para /health e /metrics responderem) e toda consulta falha como 503."""

    def __getattr__(self, nome: str) -> Any:
        def _falha(*_: Any, **__: Any) -> Any:
            raise ErroRepositorio("Supabase não configurado (SUPABASE_URL / SUPABASE_SERVICE_KEY)")

        return _falha


def _provedores(s: Settings) -> list[Provedor]:
    provs: list[Provedor] = []
    if s.cloudflare_account_id and s.cloudflare_api_token.get_secret_value():
        provs.append(
            CloudflareEmbedding(
                s.cloudflare_account_id,
                s.cloudflare_api_token.get_secret_value(),
                s.embedding_model,
                s.embedding_dim,
                s.embedding_timeout_s,
            )
        )
    if s.hf_api_token.get_secret_value():
        provs.append(
            HuggingFaceEmbedding(
                s.hf_api_token.get_secret_value(), s.hf_embedding_model, s.embedding_dim, s.embedding_timeout_s
            )
        )
    return provs


def _repo_padrao(s: Settings) -> Repositorio:
    if not s.supabase_configurado:
        log.error("Supabase não configurado: as rotas que usam o banco vão responder 503")
        return RepositorioIndisponivel()  # type: ignore[return-value]
    from app.db.supabase_repo import SupabaseRepositorio, criar_cliente

    return SupabaseRepositorio(criar_cliente(s))


def create_app(
    settings: Settings | None = None,
    *,
    repo: Repositorio | None = None,
    embeddings: CadeiaEmbeddings | None = None,
    modelo: RiskModel | object | None = _NAO_CARREGAR,
) -> FastAPI:
    s = settings or get_settings()
    configurar_logs(s.log_level)

    app = FastAPI(
        title="ASA Turbo API",
        version=s.app_version,
        summary="Agente para o Estudante (chat RAG) e Monitoramento de Risco de Evasão.",
        docs_url="/docs" if s.app_env != "producao" else None,
        redoc_url=None,
    )
    registrar_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
        max_age=600,
    )
    app.add_middleware(MiddlewareRequisicao)  # o último adicionado é o mais externo

    repo = repo if repo is not None else _repo_padrao(s)
    if embeddings is None:
        embeddings = CadeiaEmbeddings(
            _provedores(s),
            cooldown_s=s.embedding_cooldown_s,
            ao_falhar=lambda p: metricas.embedding_falhas_total.labels(p).inc(),
        )
    if modelo is _NAO_CARREGAR:
        modelo = carregar_modelo(
            s.caminho(s.risk_model_path), s.caminho(s.risk_seeds_path), s.risk_limiar_amarelo, s.risk_limiar_vermelho
        )
    indice = CacheIndiceLexical(repo, s.rag_cache_lexical_s)

    st = app.state
    st.settings = s
    st.repo = repo
    st.embeddings = embeddings
    st.validador_jwt = ValidadorJWT(s)
    st.cache_perfis = CachePerfis(s.perfil_cache_ttl_s)
    st.indice_lexical = indice
    st.servico_chat = ServicoChat(repo, embeddings, indice, s)
    st.servico_casos = ServicoCasos(repo)
    st.servico_risco = ServicoRisco(repo, modelo)  # type: ignore[arg-type]
    st.servico_documentos = ServicoDocumentos(
        repo, embeddings, indice, permitir_sem_embedding=s.rag_fallback_lexical and not embeddings.provedores
    )

    for r in (operacao.router, chat.router, casos.router, risco.router, admin.router):
        app.include_router(r)

    if not embeddings.provedores:
        log.warning("nenhum provedor de embedding configurado: o chat usará só o fallback lexical")
    log.info(
        "api pronta",
        extra={
            "versao": s.app_version,
            "ambiente": s.app_env,
            "provedores_embedding": [p.nome for p in embeddings.provedores],
            "versao_modelo_risco": getattr(modelo, "versao", None),
        },
    )
    return app


def _app_padrao() -> FastAPI:
    return create_app()


def __getattr__(nome: str) -> Any:
    # `app` é criado sob demanda (uvicorn app.main:app) para importar este módulo nos testes sem efeitos
    if nome == "app":
        global app
        app = _app_padrao()
        return app
    raise AttributeError(nome)
