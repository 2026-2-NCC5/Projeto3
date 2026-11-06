"""Valida corpos de resposta contra os schemas de docs/api-contract.yaml."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from app.core.config import PROJETO_DIR


@lru_cache
def _contrato() -> dict[str, Any]:
    with open(PROJETO_DIR / "docs" / "api-contract.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def validar(nome_schema: str, corpo: Any) -> None:
    """Levanta AssertionError listando cada violação do schema `nome_schema`."""
    doc = _contrato()
    schema = {"$ref": f"#/components/schemas/{nome_schema}", "components": doc["components"]}
    erros = sorted(Draft202012Validator(schema).iter_errors(corpo), key=lambda e: list(e.path))
    assert not erros, "\n".join(f"{list(e.path)}: {e.message}" for e in erros[:10])
