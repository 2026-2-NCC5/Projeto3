"""Checagem de groundedness por sobreposição: a resposta só afirma o que está nos trechos?

Regras (por frase da resposta):
1. **Números** (prazos, quantidades, percentuais) precisam aparecer nos trechos.
   É o erro mais grave num agente de atendimento ("15 dias" virar "30 dias").
2. Pelo menos ``cobertura_min`` dos termos de conteúdo da frase (sem stopwords,
   com radical simples) precisam estar nos trechos.

Uma frase que falha em qualquer regra é "sem suporte". O score da resposta é a
fração de frases com suporte. Respostas de abstenção não são avaliadas.
"""

from __future__ import annotations

import re
from typing import Any

from .recuperacao import STOPWORDS, normalizar

EXTRA_STOP = {"pode", "deve", "ser", "sao", "estao", "esta", "voce", "sua", "seu", "pelo", "pela", "ate", "apos",
              "caso", "quando", "onde", "mais", "menos", "cada", "todos", "todas", "sem", "nao", "sim"}
NUMEROS_EXTENSO = {"um": "1", "uma": "1", "dois": "2", "duas": "2", "tres": "3", "quatro": "4", "cinco": "5",
                   "dez": "10", "quinze": "15", "vinte": "20", "trinta": "30", "noventa": "90"}


def _radical(t: str) -> str:
    return t[:6]


def _termos(texto: str) -> set[str]:
    return {_radical(t) for t in normalizar(texto).split()
            if len(t) > 2 and t not in STOPWORDS and t not in EXTRA_STOP and not t.isdigit()}


def _numeros(texto: str) -> set[str]:
    norm = normalizar(texto)
    nums = set(re.findall(r"\d+", norm))
    nums |= {NUMEROS_EXTENSO[t] for t in norm.split() if t in NUMEROS_EXTENSO}
    return nums


def frases(texto: str) -> list[str]:
    return [f.strip() for f in re.split(r"(?<=[.!?;])\s+|\n+", texto) if len(f.strip()) > 3]


def verificar(resposta: str, trechos: list[str], cobertura_min: float = 0.7) -> dict[str, Any]:
    base = " ".join(trechos)
    termos_base, nums_base = _termos(base), _numeros(base)
    resultado = []
    for f in frases(resposta):
        termos = _termos(f)
        cobertura = len(termos & termos_base) / len(termos) if termos else 1.0
        nums_sem = sorted(_numeros(f) - nums_base)
        ok = cobertura >= cobertura_min and not nums_sem
        resultado.append({"frase": f, "cobertura": round(cobertura, 3), "numeros_sem_suporte": nums_sem, "suportada": ok})
    n = len(resultado) or 1
    return {
        "score": round(sum(r["suportada"] for r in resultado) / n, 4),
        "fundamentada": all(r["suportada"] for r in resultado),
        "frases": resultado,
    }
