"""Reescrita de perguntas de continuação usando o histórico.

Ex.: histórico "Como faço o trancamento de matrícula?" + pergunta "e o prazo?"
-> consulta "Como faço o trancamento de matrícula? prazo".

Determinística e sem LLM: só junta o assunto da pergunta anterior do
estudante à pergunta atual quando ela, sozinha, não tem assunto suficiente.
Nada é inventado: a consulta usa apenas palavras que o estudante escreveu.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.rag.texto import normalizar, tokens

# Começos típicos de pergunta de continuação ("e o prazo?", "mas e se...", "e pra EAD?")
_CONECTORES = re.compile(
    r"^(e|mas|entao|tambem|alem disso|e quanto|e sobre|e se|e no caso|nesse caso|neste caso|"
    r"e pra|e para|e o|e a|e os|e as|e no|e na|e quem|e onde|e como|e quando|e qual|e quais|"
    r"e quanto custa|quanto custa|qual o prazo|ate quando|e depois)\b"
)
# Referências ao assunto anterior
_ANAFORAS = frozenset(
    [
        "isso",
        "isto",
        "disso",
        "disto",
        "nisso",
        "nisto",
        "dele",
        "dela",
        "deles",
        "delas",
        "esse",
        "essa",
        "esses",
        "essas",
        "este",
        "esta",
        "estes",
        "estas",
        "desse",
        "dessa",
        "deste",
        "desta",
        "nesse",
        "nessa",
        "neste",
        "nesta",
        "ele",
        "ela",
        "la",
        "lo",
        "mesmo",
        "mesma",
        "tal",
    ]
)
_MAX_TOKENS_CONTINUACAO = 3


@dataclass(frozen=True)
class Mensagem:
    papel: str  # 'estudante' | 'agente'
    conteudo: str


@dataclass(frozen=True)
class Reescrita:
    consulta: str
    reescrita: bool
    base: str | None = None  # pergunta anterior usada como contexto


def eh_continuacao(pergunta: str) -> bool:
    norm = normalizar(pergunta)
    if not norm:
        return False
    conteudo = tokens(pergunta)
    palavras = set(norm.split())
    if _CONECTORES.match(norm) and len(conteudo) <= 4:
        return True
    if palavras & _ANAFORAS and len(conteudo) <= 4:
        return True
    return len(conteudo) <= _MAX_TOKENS_CONTINUACAO - 2  # 0 ou 1 palavra de conteúdo


def _limpar_conector(pergunta: str) -> str:
    texto = pergunta.strip()
    m = re.match(r"^\s*(e|mas|entao|então|tambem|também)\s+", texto, flags=re.IGNORECASE)
    return texto[m.end() :] if m else texto


def reescrever_pergunta(pergunta: str, historico: Sequence[Mensagem]) -> Reescrita:
    """Função pura. `historico` em ordem cronológica (mais antiga primeiro)."""
    pergunta = pergunta.strip()
    anteriores = [m.conteudo.strip() for m in historico if m.papel == "estudante" and m.conteudo.strip()]
    if not anteriores or not eh_continuacao(pergunta):
        return Reescrita(consulta=pergunta, reescrita=False)

    # Usa a pergunta anterior "com assunto". Se ela também era continuação,
    # sobe mais uma (ex.: "trancamento?" -> "e o prazo?" -> "e pra EAD?").
    base_partes: list[str] = []
    for anterior in reversed(anteriores[-3:]):
        base_partes.insert(0, anterior)
        if not eh_continuacao(anterior):
            break
    base = " ".join(base_partes)
    atual = _limpar_conector(pergunta)
    return Reescrita(consulta=f"{base} {atual}".strip(), reescrita=True, base=base)
