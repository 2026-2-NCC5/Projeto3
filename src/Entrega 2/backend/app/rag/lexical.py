"""Índice lexical TF-IDF em memória (fallback quando não há embedding).

Por que não usar o `idf_table.json` da Entrega 1 contra o pgvector: os
embeddings da base são bge-m3 (1024d); um vetor TF-IDF não é comparável a
eles (docs/decisoes/0001-fase0.md). Por isso o fallback NÃO mistura espaços:
ele roda localmente, sobre o texto dos trechos ativos, com IDF calculado da
própria base, e tem limiar próprio (RAG_LIMIAR_LEXICAL).
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.rag.texto import tokens


@dataclass(frozen=True)
class _Doc:
    pesos: dict[str, float]
    meta: dict[str, Any]


class IndiceLexical:
    def __init__(self, docs: list[_Doc], idf: dict[str, float]) -> None:
        self._docs = docs
        self._idf = idf
        self._idf_padrao = max(idf.values(), default=1.0)
        # índice invertido: termo -> posições dos docs
        self._invertido: dict[str, list[int]] = {}
        for i, d in enumerate(docs):
            for termo in d.pesos:
                self._invertido.setdefault(termo, []).append(i)

    def __len__(self) -> int:
        return len(self._docs)

    @staticmethod
    def _vetor(contagem: Counter[str], idf: dict[str, float], idf_padrao: float) -> dict[str, float]:
        pesos = {t: (1 + math.log(c)) * idf.get(t, idf_padrao) for t, c in contagem.items()}
        norma = math.sqrt(sum(v * v for v in pesos.values())) or 1.0
        return {t: v / norma for t, v in pesos.items()}

    @classmethod
    def construir(
        cls, chunks: Sequence[dict[str, Any]], campo_texto: str = "conteudo", campo_titulo: str = "titulo_documento"
    ) -> IndiceLexical:
        """`chunks`: dicts com o texto e metadados (devolvidos inteiros na busca).
        O título do documento entra no texto indexado (peso de 1 ocorrência extra)."""
        contagens = []
        df: Counter[str] = Counter()
        for c in chunks:
            texto = f"{c.get(campo_titulo) or ''} {c.get(campo_texto) or ''}"
            cont = Counter(tokens(texto))
            contagens.append(cont)
            df.update(cont.keys())
        n = max(len(chunks), 1)
        idf = {t: math.log((1 + n) / (1 + f)) + 1 for t, f in df.items()}
        padrao = max(idf.values(), default=1.0)
        docs = [_Doc(cls._vetor(cont, idf, padrao), dict(c)) for cont, c in zip(contagens, chunks, strict=True)]
        return cls(docs, idf)

    def buscar(self, consulta: str, limite: int = 3) -> list[tuple[dict[str, Any], float]]:
        """Devolve [(metadados do chunk, similaridade de cosseno TF-IDF)], maior primeiro."""
        cont = Counter(tokens(consulta))
        if not cont or not self._docs:
            return []
        # termos fora do vocabulário não ajudam a achar nada; só diluem a norma da consulta
        q = self._vetor(cont, self._idf, self._idf_padrao)
        pontos: dict[int, float] = {}
        for termo, peso in q.items():
            for i in self._invertido.get(termo, ()):
                pontos[i] = pontos.get(i, 0.0) + peso * self._docs[i].pesos[termo]
        melhores = sorted(pontos.items(), key=lambda kv: -kv[1])[:limite]
        return [(self._docs[i].meta, round(min(max(s, 0.0), 1.0), 4)) for i, s in melhores]
