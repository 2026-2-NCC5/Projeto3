from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.core.config import PROJETO_DIR, Settings
from app.main import create_app
from app.rag.embeddings import CadeiaEmbeddings
from app.risk.modelo import ModeloSklearn, treinar_placeholder
from tests.fakes import SEGREDO_JWT, ProvedorFalso, RepoMemoria


def settings_teste(**extra: object) -> Settings:
    base = dict(
        app_env="teste",
        supabase_jwt_secret=SEGREDO_JWT,
        supabase_url="",
        supabase_service_key="",
        cloudflare_account_id="",
        cloudflare_api_token="",
        hf_api_token="",
        log_level="WARNING",
        chat_rate_limit_por_minuto=1000,
        cors_origins="http://localhost:5173",
    )
    base.update(extra)
    return Settings(_env_file=None, **base)  # type: ignore[call-arg]


@pytest.fixture(scope="session")
def modelo() -> ModeloSklearn:
    return treinar_placeholder(PROJETO_DIR / "seeds" / "estudantes_sinteticos.csv")


@dataclass
class Ambiente:
    client: TestClient
    repo: RepoMemoria
    provedor: ProvedorFalso
    reserva: ProvedorFalso
    app: object


@pytest.fixture
def amb(modelo: ModeloSklearn) -> Iterator[Ambiente]:
    repo = RepoMemoria()
    principal, reserva = ProvedorFalso("cloudflare"), ProvedorFalso("huggingface")
    cadeia = CadeiaEmbeddings([principal, reserva], cooldown_s=0)
    app = create_app(settings_teste(), repo=repo, embeddings=cadeia, modelo=modelo)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield Ambiente(client, repo, principal, reserva, app)
