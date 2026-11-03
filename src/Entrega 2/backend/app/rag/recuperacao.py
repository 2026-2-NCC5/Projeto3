"""Núcleo do RAG: reescrita -> vetorização -> busca -> decisão (responder ou abster).

`recuperar()` é PURA em relação à infraestrutura: recebe as funções de
vetorizar e buscar por parâmetro. A sessão de ML usa assim para avaliar:

    from app.rag import ConfigRAG, recuperar
    r = recuperar("Como tiro o atestado?", [], vetorizar=meu_embed,
                  buscar_vetorial=minha_busca, config=ConfigRAG(limiar=0.55))
    r.abstencao, r.confianca, [t.titulo for t in r.trechos]

Sem I/O, sem métricas, sem banco: o serviço do chat é que persiste e mede.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from app.rag.embeddings import FalhaVetorizacao, Vetorizacao
from app.rag.lexical import IndiceLexical
from app.rag.reescrita import Mensagem, reescrever_pergunta


class FalhaBusca(Exception):
    """A base de conhecimento não pôde ser consultada."""


Motivo = Literal["baixa_similaridade", "sem_documentos", "falha_vetorizacao", "falha_busca"]
Metodo = Literal["vetorial", "lexical", "nenhum"]


@dataclass(frozen=True)
class ConfigRAG:
    limiar: float = 0.55  # cosseno bge-m3 (medição em web/api/perguntar.py)
    top_k: int = 3
    fallback_lexical: bool = True
    limiar_lexical: float = 0.35  # cosseno TF-IDF (calibrado na base oficial; ver README)


@dataclass(frozen=True)
class Trecho:
    chunk_id: str
    documento_id: str | None
    conteudo: str
    similaridade: float
    titulo: str
    fonte: str
    data_atualizacao: Any

    @classmethod
    def de_linha(cls, linha: dict[str, Any], similaridade: float | None = None) -> Trecho:
        """Aceita o formato da RPC buscar_chunks_similares."""
        return cls(
            chunk_id=str(linha.get("chunk_id") or linha.get("id")),
            documento_id=str(linha["documento_id"]) if linha.get("documento_id") else None,
            conteudo=linha.get("conteudo") or "",
            similaridade=round(float(similaridade if similaridade is not None else linha.get("similaridade") or 0), 4),
            titulo=linha.get("titulo_documento") or linha.get("titulo") or "Documento sem título",
            fonte=linha.get("fonte_documento") or linha.get("fonte") or "",
            data_atualizacao=linha.get("data_atualizacao"),
        )


@dataclass
class Recuperacao:
    pergunta: str
    consulta: str
    reescrita: bool
    metodo: Metodo
    trechos: list[Trecho]
    confianca: float
    abstencao: bool
    motivo_abstencao: Motivo | None
    limiar_aplicado: float
    provedor: str | None = None
    modelo_embedding: str | None = None
    falhas: list[str] = field(default_factory=list)

    @property
    def usou_fallback(self) -> bool:
        return self.metodo == "lexical"


VetorizarFn = Callable[[str], Vetorizacao]
BuscarFn = Callable[[list[float], int], Sequence[dict[str, Any]]]
IndiceFn = Callable[[], IndiceLexical | None]


def _decidir(base: dict[str, Any], trechos: list[Trecho], limiar: float) -> Recuperacao:
    if not trechos:
        return Recuperacao(
            **base, trechos=[], confianca=0.0, abstencao=True, motivo_abstencao="sem_documentos", limiar_aplicado=limiar
        )
    confianca = trechos[0].similaridade
    if confianca < limiar:
        return Recuperacao(
            **base,
            trechos=trechos,
            confianca=confianca,
            abstencao=True,
            motivo_abstencao="baixa_similaridade",
            limiar_aplicado=limiar,
        )
    return Recuperacao(
        **base, trechos=trechos, confianca=confianca, abstencao=False, motivo_abstencao=None, limiar_aplicado=limiar
    )


def _lexical(indice_fn: IndiceFn | None, consulta: str, top_k: int) -> list[Trecho] | None:
    if indice_fn is None:
        return None
    try:
        indice = indice_fn()
    except Exception:  # noqa: BLE001 - sem índice, segue para abstenção
        return None
    if indice is None or len(indice) == 0:
        return None
    resultados = indice.buscar(consulta, top_k)
    if not resultados:
        return []
    # Busca por palavras acha o DOCUMENTO certo, mas tende a preferir os trechos curtos
    # ("Condições", "Atendimento") ao trecho principal. Como os documentos da base são
    # curtos, o melhor documento entra inteiro, na ordem original, com a similaridade
    # dele; os demais resultados vêm depois, como alternativas.
    melhor_meta, melhor_sim = resultados[0]
    doc_id = melhor_meta.get("documento_id")
    do_doc = indice.trechos_do_documento(doc_id) if doc_id else []
    if not do_doc:
        return [Trecho.de_linha(meta, sim) for meta, sim in resultados]
    vistos = {str(m.get("chunk_id")) for m in do_doc}
    outros = [(m, s) for m, s in resultados if str(m.get("chunk_id")) not in vistos]
    return [Trecho.de_linha(m, melhor_sim) for m in do_doc] + [Trecho.de_linha(m, s) for m, s in outros]


def recuperar(
    pergunta: str,
    historico: Sequence[Mensagem] = (),
    *,
    vetorizar: VetorizarFn,
    buscar_vetorial: BuscarFn,
    indice_lexical: IndiceFn | None = None,
    config: ConfigRAG = ConfigRAG(),
) -> Recuperacao:
    r = reescrever_pergunta(pergunta, historico)
    falhas: list[str] = []
    motivo_falha: Motivo | None = None
    vet: Vetorizacao | None = None

    try:
        vet = vetorizar(r.consulta)
    except FalhaVetorizacao as e:
        falhas.append(f"vetorizacao: {e}")
        motivo_falha = "falha_vetorizacao"

    if vet is not None:
        try:
            linhas = buscar_vetorial(vet.vetor, config.top_k)
            base = dict(
                pergunta=pergunta,
                consulta=r.consulta,
                reescrita=r.reescrita,
                metodo="vetorial",
                provedor=vet.provedor,
                modelo_embedding=vet.modelo,
                falhas=falhas,
            )
            trechos = [Trecho.de_linha(linha) for linha in linhas]
            trechos.sort(key=lambda t: -t.similaridade)
            return _decidir(base, trechos, config.limiar)
        except FalhaBusca as e:
            falhas.append(f"busca: {e}")
            motivo_falha = "falha_busca"

    # Fallback lexical (TF-IDF local, nunca misturado ao pgvector)
    if config.fallback_lexical:
        trechos_lex = _lexical(indice_lexical, r.consulta, config.top_k)
        if trechos_lex is not None:
            base = dict(
                pergunta=pergunta,
                consulta=r.consulta,
                reescrita=r.reescrita,
                metodo="lexical",
                provedor="tfidf",
                modelo_embedding="tfidf-local",
                falhas=falhas,
            )
            return _decidir(base, trechos_lex, config.limiar_lexical)

    return Recuperacao(
        pergunta=pergunta,
        consulta=r.consulta,
        reescrita=r.reescrita,
        metodo="nenhum",
        trechos=[],
        confianca=0.0,
        abstencao=True,
        motivo_abstencao=motivo_falha or "falha_vetorizacao",
        limiar_aplicado=config.limiar,
        falhas=falhas,
    )
