"""Configuração por variáveis de ambiente (pydantic-settings).

Lê `src/Entrega 2/.env` (raiz do projeto) e, se existir, `backend/.env`.
Variáveis do ambiente têm prioridade sobre os arquivos.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# app/core/config.py -> parents[2] = backend/, parents[3] = raiz do projeto
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJETO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJETO_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- aplicação
    app_env: Literal["local", "teste", "producao"] = "local"
    app_version: str = "0.9.0"
    log_level: str = "INFO"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:8080"]
    )
    chat_rate_limit_por_minuto: int = 20

    # --- Supabase
    supabase_url: str = ""
    supabase_service_key: SecretStr = SecretStr("")
    supabase_jwt_secret: SecretStr = SecretStr("")
    jwt_audience: str = "authenticated"
    supabase_timeout_s: float = 10.0
    perfil_cache_ttl_s: float = 30.0

    # --- embeddings (mesmo espaço vetorial: bge-m3, 1024d)
    cloudflare_account_id: str = ""
    cloudflare_api_token: SecretStr = SecretStr("")
    embedding_model: str = "@cf/baai/bge-m3"
    hf_api_token: SecretStr = SecretStr("")
    hf_embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    embedding_timeout_s: float = 8.0
    embedding_cooldown_s: float = 30.0

    # --- RAG
    confidence_threshold: float = Field(0.55, ge=0, le=1)
    rag_top_k: int = Field(3, ge=1, le=10)
    rag_historico_max: int = Field(6, ge=0, le=20)
    rag_fallback_lexical: bool = True
    rag_limiar_lexical: float = Field(0.35, ge=0, le=1)
    rag_cache_lexical_s: float = 600.0
    rag_versao: str = "rag-0.9"

    # --- modelo de risco
    risk_model_path: str = "ml/artifacts/risco_v2.joblib"
    risk_model_version: str = "risco-2.0.0"
    risk_seeds_path: str = "seeds/estudantes_sinteticos.csv"
    risk_limiar_amarelo: float = 0.30
    risk_limiar_vermelho: float = 0.60

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _separar_origens(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    def caminho(self, relativo: str) -> Path:
        """Resolve caminhos relativos à raiz do projeto (src/Entrega 2)."""
        p = Path(relativo)
        return p if p.is_absolute() else PROJETO_DIR / p

    @property
    def supabase_configurado(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
