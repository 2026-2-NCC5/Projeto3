"""Normalização e tokenização de texto em português (sem dependências)."""

from __future__ import annotations

import re
import unicodedata

STOPWORDS = frozenset(
    [
        "a",
        "o",
        "as",
        "os",
        "um",
        "uma",
        "uns",
        "umas",
        "de",
        "da",
        "do",
        "das",
        "dos",
        "d",
        "em",
        "no",
        "na",
        "nos",
        "nas",
        "num",
        "numa",
        "por",
        "pelo",
        "pela",
        "pelos",
        "pelas",
        "para",
        "pra",
        "pro",
        "pras",
        "pros",
        "com",
        "sem",
        "sob",
        "sobre",
        "ao",
        "aos",
        "a",
        "à",
        "às",
        "e",
        "ou",
        "mas",
        "que",
        "se",
        "ja",
        "já",
        "nao",
        "não",
        "sim",
        "eu",
        "tu",
        "ele",
        "ela",
        "nos",
        "nós",
        "vos",
        "eles",
        "elas",
        "me",
        "te",
        "lhe",
        "lhes",
        "mim",
        "ti",
        "si",
        "meu",
        "minha",
        "meus",
        "minhas",
        "teu",
        "tua",
        "seu",
        "sua",
        "seus",
        "suas",
        "nosso",
        "nossa",
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
        "isso",
        "isto",
        "aquele",
        "aquela",
        "aquilo",
        "la",
        "lá",
        "aqui",
        "ai",
        "aí",
        "entao",
        "então",
        "tambem",
        "também",
        "mais",
        "menos",
        "muito",
        "muita",
        "muitos",
        "muitas",
        "ainda",
        "depois",
        "antes",
        "quando",
        "onde",
        "como",
        "qual",
        "quais",
        "quem",
        "cujo",
        "porque",
        "pois",
        "ser",
        "sou",
        "e",
        "é",
        "era",
        "foi",
        "sao",
        "são",
        "estar",
        "esta",
        "está",
        "estou",
        "tem",
        "ter",
        "tenho",
        "temos",
        "ha",
        "há",
        "vou",
        "vai",
        "vamos",
        "fazer",
        "faço",
        "faz",
        "posso",
        "pode",
        "podem",
        "preciso",
        "precisa",
        "queria",
        "quero",
        "gostaria",
        "saber",
        "sobre",
        "olá",
        "ola",
        "oi",
        "bom",
        "boa",
        "dia",
        "tarde",
        "noite",
        "obrigado",
        "obrigada",
        "favor",
        "gentileza",
        "alguem",
        "alguém",
        "algum",
        "alguma",
        "algo",
        "coisa",
    ]
)


def sem_acento(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalizar(texto: str) -> str:
    """minúsculas, sem acento, só letras/dígitos separados por espaço."""
    t = sem_acento(texto.lower())
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def radical(token: str) -> str:
    """Stemming leve: plural e algumas terminações comuns."""
    if len(token) <= 4:
        return token
    for suf, novo in (
        ("coes", "cao"),
        ("oes", "ao"),
        ("aes", "ao"),
        ("ais", "al"),
        ("eis", "el"),
        ("res", "r"),
        ("ns", "m"),
    ):
        if token.endswith(suf):
            return token[: -len(suf)] + novo
    if token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def tokens(texto: str, *, manter_stopwords: bool = False) -> list[str]:
    """Tokens normalizados e com radical. Remove stopwords e tokens de 1 letra."""
    saida = []
    for t in normalizar(texto).split():
        if len(t) < 2 and not t.isdigit():
            continue
        if not manter_stopwords and t in STOPWORDS:
            continue
        saida.append(radical(t))
    return saida
