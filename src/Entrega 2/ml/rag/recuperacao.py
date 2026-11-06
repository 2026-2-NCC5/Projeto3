"""Recuperação local para avaliar o RAG, com a mesma interface do backend.

``backend/app/rag/`` ainda não existe. Este módulo reproduz, em memória:

- a RPC ``buscar_chunks_similares(query_embedding, limite, limiar_similaridade)``
  (mesmas colunas de saída: chunk_id, documento_id, conteudo, similaridade,
  titulo_documento, fonte_documento, data_atualizacao);
- ``processar_pergunta`` do ``web/api/perguntar.py`` (resposta extrativa do
  trecho top-1, abstenção abaixo do limiar, evidências).

Quando o backend tiver o módulo dele, basta trocar o ``Recuperador`` por uma
chamada ao banco: o avaliador só depende de ``buscar`` e ``processar_pergunta``.
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]  # src/Entrega 2
SEED_FICTICIO = RAIZ.parent / "Entrega 1" / "seed_v2.sql"

TEXTO_ABSTENCAO = (
    "Não encontrei essa informação com confiança suficiente nas fontes "
    "oficiais disponíveis. Vou te encaminhar para um atendente do ASA."
)


# ---------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    documento_id: str
    ordem: int
    conteudo: str
    titulo_documento: str
    fonte_documento: str
    data_atualizacao: str


def carregar_corpus(caminho: Path = SEED_FICTICIO) -> list[Chunk]:
    """Lê documentos e chunks do seed SQL (20 documentos fictícios da Entrega 1)."""
    sql = caminho.read_text(encoding="utf-8")
    docs = {
        m[0]: {"titulo": m[1], "fonte": m[3], "data": m[4]}
        for m in re.findall(r"\('([0-9a-f-]{36})', '([^']*)', '([^']*)', '([^']*)', \d+, '([^']*)'\)", sql)
    }
    chunks = []
    for doc_id, ordem, conteudo in re.findall(r"\('([0-9a-f-]{36})', (\d+), '((?:[^']|'')*)'\)", sql):
        d = docs[doc_id]
        cid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}/{ordem}"))
        chunks.append(Chunk(cid, doc_id, int(ordem), conteudo.replace("''", "'"), d["titulo"], d["fonte"], d["data"]))
    return chunks


# ---------------------------------------------------------------------------
# Vetorizadores
# ---------------------------------------------------------------------------

class Vetorizador(Protocol):
    nome: str

    def ajustar(self, textos: list[str]) -> None: ...
    def vetorizar(self, textos: list[str], consulta: bool) -> np.ndarray: ...


# Tokenização da Entrega 1 (src/Entrega 1/api/perguntar.py), copiada para a comparação ser fiel.
STOPWORDS = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "que", "e", "é", "para", "com",
    "um", "uma", "no", "na", "nos", "nas", "em", "por", "se", "meu", "minha", "tenho",
    "preciso", "como", "qual", "quais", "sobre", "ao", "aos", "esse", "essa", "isso",
    "eu", "voce", "você", "tem", "ter", "vou", "vai", "sera", "será", "ser", "sao", "são",
    "ou", "mais", "muito", "ja", "já", "ainda", "depois", "antes", "entao", "então",
}
_SIN_GRUPOS = {
    "trancar": "suspender suspendo suspensao pausar pauso parar paro trancamento tranco trancando trancado",
    "cancelamento": "cancelar cancelo cancelado desistir desistencia",
    "financeiro": "boleto boletos mensalidade mensalidades pagamento pagar divida desconto valor preco",
    "auxiliofinanceiro": "auxilio emergencial vulnerabilidade",
    "declaracao": "comprovante comprovantes atestado declaracoes certidao",
    "financiamento": "fies prouni bolsas bolsa bolsista financiado",
    "desempenho": "reprovado reprovacao reprovar reprovando nota notas media falta faltas faltei frequencia presenca",
    "avaliacao": "prova provas exame teste",
    "segundachamada": "2achamada reposicao perdi",
    "revisaonota": "revisao recurso contestar errada corrigir",
    "aproveitamento": "dispensa dispensar equivalencia aproveitar",
    "transferencia": "trocar troca mudar mudanca transferir",
    "turno": "periodo horario",
    "estagio": "estagiar estagiario",
    "tcc": "monografia orientador orientacao",
    "biblioteca": "livro livros emprestimo emprestar devolver devolucao",
    "carreira": "emprego vaga vagas curriculo entrevista",
    "atestadomedico": "medico saude doente doenca",
    "certificado": "diploma formatura colacao formar",
    "intercambio": "exterior fora",
}
SINONIMOS = {v: k for k, vs in _SIN_GRUPOS.items() for v in vs.split()}


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9\s]", " ", texto)


def tokenizar(texto: str) -> list[str]:
    toks = [t for t in normalizar(texto).split() if len(t) > 2 and t not in STOPWORDS]
    return [SINONIMOS.get(t, t) for t in toks]


class TfidfHashing:
    """Hashing trick (MD5 mod 384) + TF log; com ``usar_idf`` aplica a tabela IDF da E1."""

    def __init__(self, usar_idf: bool, dim: int = 384):
        self.dim, self.usar_idf = dim, usar_idf
        self.nome = "tfidf_hashing_idf" if usar_idf else "tfidf_hashing"
        self.idf = np.ones(dim)

    def _bucket(self, tok: str) -> int:
        return int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16) % self.dim

    def ajustar(self, textos: list[str]) -> None:
        if not self.usar_idf:
            return
        df = np.zeros(self.dim)
        for t in textos:
            for b in {self._bucket(tok) for tok in tokenizar(t)}:
                df[b] += 1
        self.idf = np.log((len(textos) + 1) / (df + 1)) + 1  # mesma fórmula do calcular_idf da E1

    def vetorizar(self, textos: list[str], consulta: bool) -> np.ndarray:
        M = np.zeros((len(textos), self.dim))
        for i, t in enumerate(textos):
            cont: dict[str, int] = {}
            for tok in tokenizar(t):
                cont[tok] = cont.get(tok, 0) + 1
            for tok, c in cont.items():
                b = self._bucket(tok)
                M[i, b] += (1 + math.log(c)) * self.idf[b]
        n = np.linalg.norm(M, axis=1, keepdims=True)
        return np.divide(M, n, out=np.zeros_like(M), where=n > 0)


class EmbeddingDenso:
    """Modelos sentence-transformers (rodam localmente na CPU)."""

    def __init__(self, nome: str, modelo: str, prefixo_consulta: str = "", prefixo_documento: str = ""):
        self.nome, self.modelo = nome, modelo
        self.pq, self.pd = prefixo_consulta, prefixo_documento
        self._m = None

    def ajustar(self, textos: list[str]) -> None:
        from sentence_transformers import SentenceTransformer

        self._m = SentenceTransformer(self.modelo, device="cpu")

    def vetorizar(self, textos: list[str], consulta: bool) -> np.ndarray:
        pre = self.pq if consulta else self.pd
        return np.asarray(self._m.encode([pre + t for t in textos], normalize_embeddings=True, batch_size=32))


# ---------------------------------------------------------------------------
# Recuperador
# ---------------------------------------------------------------------------

def montar_consulta(pergunta: str, contexto: list[str] | None = None, janela: int = 1) -> str:
    """Contexto da conversa: as últimas ``janela`` mensagens do estudante entram na consulta."""
    anteriores = (contexto or [])[-janela:] if janela else []
    return " ".join([*anteriores, pergunta]).strip()


class Recuperador:
    def __init__(self, vetorizador: Vetorizador, chunks: list[Chunk] | None = None):
        self.v = vetorizador
        self.chunks = chunks if chunks is not None else carregar_corpus()
        textos = [c.conteudo for c in self.chunks]
        self.v.ajustar(textos)
        self.E = self.v.vetorizar(textos, consulta=False)

    def buscar_chunks_similares(self, query_embedding: np.ndarray, limite: int = 3,
                                limiar_similaridade: float = 0.0) -> list[dict[str, Any]]:
        sims = self.E @ query_embedding
        ordem = np.argsort(-sims)
        out = []
        for i in ordem:
            if sims[i] < limiar_similaridade or len(out) >= limite:
                break
            c = self.chunks[i]
            out.append({"chunk_id": c.chunk_id, "documento_id": c.documento_id, "conteudo": c.conteudo,
                        "similaridade": float(sims[i]), "titulo_documento": c.titulo_documento,
                        "fonte_documento": c.fonte_documento, "data_atualizacao": c.data_atualizacao})
        return out

    def buscar(self, pergunta: str, contexto: list[str] | None = None, limite: int = 3) -> list[dict[str, Any]]:
        q = self.v.vetorizar([montar_consulta(pergunta, contexto)], consulta=True)[0]
        return self.buscar_chunks_similares(q, limite=limite)

    def processar_pergunta(self, pergunta: str, contexto: list[str] | None = None,
                           limiar: float = 0.55) -> dict[str, Any]:
        """Mesmo formato de web/api/perguntar.py."""
        chunks = self.buscar(pergunta, contexto)
        evid = [{"titulo": c["titulo_documento"], "fonte": c["fonte_documento"], "similaridade": round(c["similaridade"], 4),
                 "atualizado_em": c["data_atualizacao"], "trecho": c["conteudo"]} for c in chunks]
        if not chunks or chunks[0]["similaridade"] < limiar:
            conf = chunks[0]["similaridade"] if chunks else 0.0
            return {"resposta": TEXTO_ABSTENCAO, "confianca": round(conf, 4), "abstencao": True, "evidencias": evid}
        return {"resposta": chunks[0]["conteudo"], "confianca": round(chunks[0]["similaridade"], 4),
                "abstencao": False, "evidencias": evid}
