"""Divisão de documentos em trechos (chunks) para indexação."""

from __future__ import annotations

import re

TAMANHO_ALVO = 700
TAMANHO_MAX = 1000


def _frases(paragrafo: str) -> list[str]:
    return [f.strip() for f in re.split(r"(?<=[.!?;])\s+", paragrafo) if f.strip()]


def dividir_em_chunks(
    conteudo: str, titulo: str | None = None, alvo: int = TAMANHO_ALVO, maximo: int = TAMANHO_MAX
) -> list[str]:
    """Agrupa parágrafos até ~`alvo` caracteres; parágrafo longo é quebrado por frases.
    Cada chunk recebe o título como prefixo (igual à base atual: "Título: texto"),
    o que melhora a busca e a fonte citada."""
    paragrafos = [p.strip() for p in re.split(r"\n\s*\n", conteudo.strip()) if p.strip()]
    pedacos: list[str] = []
    for p in paragrafos:
        if len(p) <= maximo:
            pedacos.append(p)
            continue
        atual = ""
        for f in _frases(p):
            if atual and len(atual) + len(f) + 1 > alvo:
                pedacos.append(atual)
                atual = f
            else:
                atual = f"{atual} {f}".strip()
        if atual:
            pedacos.append(atual)

    chunks: list[str] = []
    atual = ""
    for p in pedacos:
        if atual and len(atual) + len(p) + 2 > alvo:
            chunks.append(atual)
            atual = p
        else:
            atual = f"{atual}\n\n{p}".strip()
    if atual:
        chunks.append(atual)
    prefixo = f"{titulo.strip()}: " if titulo else ""
    return [f"{prefixo}{c}" if prefixo and not c.startswith(prefixo) else c for c in chunks]
