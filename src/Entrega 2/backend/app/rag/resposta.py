"""Montagem da resposta SÓ com o conteúdo recuperado (extrativa, sem inventar).

A resposta é o texto dos trechos oficiais, com formatação leve:
enumerações "1) ...; 2) ..." viram passos numerados, um por linha.
Textos fixos (abstenção) são os únicos que não vêm da base.
"""

from __future__ import annotations

import re

from app.rag.recuperacao import Recuperacao, Trecho
from app.rag.texto import normalizar, tokens

TEXTO_ABSTENCAO = (
    "Não encontrei isso nos documentos oficiais com segurança suficiente. "
    "Encaminhei sua pergunta para o ASA, e um atendente vai te responder."
)
TEXTO_FALHA = (
    "Não consegui consultar a base oficial agora. Para não te passar uma informação "
    "sem fonte, encaminhei sua pergunta para o ASA."
)
MAX_CARACTERES = 900
_ENUM = re.compile(r"(?:^|[\s;:])(\d{1,2})\)\s+")


def formatar_passos(texto: str) -> str:
    """'Condições: 1) A; 2) B' -> 'Condições:\\n1. A\\n2. B'."""
    marcas = list(_ENUM.finditer(texto))
    if len(marcas) < 2:
        return texto.strip()
    cabeca = texto[: marcas[0].start()].strip().rstrip(";")
    partes = []
    for i, m in enumerate(marcas):
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        item = texto[m.end() : fim].strip().rstrip(";").strip()
        partes.append(f"{m.group(1)}. {item}")
    return "\n".join(([cabeca] if cabeca else []) + partes)


def _selecionar(trechos: list[Trecho], limiar: float) -> list[Trecho]:
    """Melhor trecho + complementos do MESMO documento que também passam no limiar."""
    principal = trechos[0]
    escolhidos = [principal]
    total = len(principal.conteudo)
    for t in trechos[1:]:
        if t.similaridade < limiar or t.documento_id != principal.documento_id:
            continue
        if total + len(t.conteudo) > MAX_CARACTERES:
            break
        escolhidos.append(t)
        total += len(t.conteudo)
    return escolhidos


_SEM_INFORMACAO = re.compile(r"^condi[cç][oõ]es:\s*n[aã]o h[aá] condi[cç][oõ]es espec[ií]ficas", re.IGNORECASE)


def _limpar(t: Trecho) -> str:
    """Tira o prefixo com o título do documento, que se repete em todo trecho da base
    ("Atestado de matrícula - Condições: ..." -> "Condições: ..."). O título já aparece na fonte."""
    texto = t.conteudo.strip()
    titulo = (t.titulo or "").strip()
    if titulo and texto.lower().startswith(titulo.lower()):
        resto = texto[len(titulo) :].lstrip()
        if resto[:1] in ("-", ":", "–"):
            texto = resto[1:].strip()
    return texto


# Continuação com pedido específico ("e o prazo?"): (o que foi pedido, como a pergunta
# pede, como uma frase do documento responde). Comparação feita sobre texto normalizado.
_ASPECTOS = (
    (
        "o prazo",
        re.compile(r"\b(prazos?|quando|data|demora|dias)\b"),
        re.compile(r"\b\d+ (dias?|meses|semanas|anos?)\b|antecedencia|\bprazos?\b|vencimento|data limite"),
    ),
    (
        "o local ou o horário de atendimento",
        re.compile(r"\b(onde|local|horarios?|atendimento|setor)\b"),
        re.compile(r"\b(setor responsavel|local|horario de atendimento)\b"),
    ),
    (
        "valores",
        re.compile(r"\b(custa|custo|valor|valores|preco|taxas?|pagar|gratis|gratuito)\b"),
        re.compile(r"\btaxas?\b|\bvalor(es)?\b|gratuit|\bcusto\b"),
    ),
)
_FRASES = re.compile(r"(?<=[.!?])\s+|\n+")
_ROTULO = re.compile(r"^(condi[cç][oõ]es|atendimento)\s*:\s*", re.IGNORECASE)
TEXTO_NAO_INFORMA = (
    "Os documentos oficiais sobre {titulo} não informam {aspecto}. "
    "Para confirmar, fale com o ASA pelos canais de atendimento."
)


def _repetida(frase: str, escolhidas: list[str]) -> bool:
    novos = set(tokens(frase))
    return any(novos and len(novos & set(tokens(e))) >= 0.7 * len(novos) for e in escolhidas)


def _focar_continuacao(rec: Recuperacao) -> tuple[str, list[Trecho]] | None:
    """Em "e o prazo?" sobre um assunto já respondido, devolve só as frases do documento
    que tratam do prazo (ou diz que o documento não informa), em vez de repetir tudo."""
    pergunta = normalizar(rec.pergunta)
    principal = rec.trechos[0]
    do_doc = [t for t in rec.trechos if t.documento_id == principal.documento_id]
    for aspecto, pede, responde in _ASPECTOS:
        if not pede.search(pergunta):
            continue
        frases: list[str] = []
        usados: list[Trecho] = []
        for t in do_doc:
            for f in _FRASES.split(_limpar(t)):
                f = _ROTULO.sub("", f.strip())
                if f and responde.search(normalizar(f)) and not _repetida(f, frases):
                    frases.append(f)
                    if t not in usados:
                        usados.append(t)
        if frases:
            return "\n".join(formatar_passos(f) for f in frases[:3]), usados
        titulo = (principal.titulo or "esse assunto").strip()
        return TEXTO_NAO_INFORMA.format(titulo=titulo, aspecto=aspecto), [principal]
    return None


def compor_resposta(rec: Recuperacao) -> tuple[str, list[Trecho]]:
    """Devolve (texto da resposta, trechos efetivamente usados)."""
    if rec.abstencao or not rec.trechos:
        texto = TEXTO_FALHA if rec.motivo_abstencao in ("falha_vetorizacao", "falha_busca") else TEXTO_ABSTENCAO
        return texto, []
    if rec.reescrita:
        focada = _focar_continuacao(rec)
        if focada:
            return focada
    usados = _selecionar(rec.trechos, rec.limiar_aplicado)
    limpos = [(t, _limpar(t)) for t in usados]
    # "Condições: não há condições específicas" não informa nada: sai da resposta
    # (a não ser que seja o único trecho).
    uteis = [(t, x) for t, x in limpos if not _SEM_INFORMACAO.match(x)] or limpos
    usados = [t for t, _ in uteis]
    blocos = [formatar_passos(x) for _, x in uteis]
    texto = "\n\n".join(b for b in blocos if b)
    if len(texto) > MAX_CARACTERES:
        corte = texto.rfind(". ", 0, MAX_CARACTERES)
        texto = texto[: corte + 1 if corte > 0 else MAX_CARACTERES].rstrip() + " (continua na fonte)"
    return texto, usados
