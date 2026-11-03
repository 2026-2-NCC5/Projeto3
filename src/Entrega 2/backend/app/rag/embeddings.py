"""Provedores de embedding (todos no MESMO espaço: bge-m3, 1024d) e a cadeia com fallback.

Ordem padrão: Cloudflare Workers AI (@cf/baai/bge-m3) -> Hugging Face
Inference (BAAI/bge-m3). Os dois servem o mesmo modelo, então os vetores são
comparáveis aos já gravados no banco. Um provedor que falha fica em espera
(cooldown) por alguns segundos para não somar timeouts em toda pergunta.
Se todos falharem, `FalhaVetorizacao` sobe e o RAG decide (fallback lexical
ou abstenção).
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

log = logging.getLogger("asa.rag.embeddings")


class FalhaVetorizacao(Exception):
    """Nenhum provedor conseguiu gerar o vetor."""


class Provedor(Protocol):
    nome: str
    modelo: str

    def vetorizar(self, textos: Sequence[str]) -> list[list[float]]: ...


def normalizar_l2(v: Sequence[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v] if n > 0 else list(v)


def _validar(vetores: Any, dim: int, qtd: int) -> list[list[float]]:
    if not isinstance(vetores, list) or not vetores:
        raise FalhaVetorizacao("resposta sem vetores")
    if not isinstance(vetores[0], list):
        vetores = [vetores]
    if len(vetores) != qtd:
        raise FalhaVetorizacao(f"{len(vetores)} vetores para {qtd} textos")
    saida = []
    for v in vetores:
        if len(v) != dim:
            raise FalhaVetorizacao(f"embedding com {len(v)} dimensões, esperado {dim}")
        saida.append(normalizar_l2([float(x) for x in v]))
    return saida


class CloudflareEmbedding:
    nome = "cloudflare"

    def __init__(
        self, account_id: str, token: str, modelo: str, dim: int, timeout_s: float, cliente: httpx.Client | None = None
    ) -> None:
        self.modelo = modelo
        self._url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{modelo}"
        self._token = token
        self._dim = dim
        self._cliente = cliente or httpx.Client(timeout=timeout_s)

    def vetorizar(self, textos: Sequence[str]) -> list[list[float]]:
        try:
            r = self._cliente.post(
                self._url, headers={"Authorization": f"Bearer {self._token}"}, json={"text": list(textos)}
            )
        except httpx.HTTPError as e:
            raise FalhaVetorizacao(f"{type(e).__name__}: {e}") from e
        if r.status_code != 200:
            raise FalhaVetorizacao(f"HTTP {r.status_code}")
        try:
            payload = r.json()
        except ValueError as e:
            raise FalhaVetorizacao("resposta não é JSON") from e
        if isinstance(payload, dict) and payload.get("success") is False:
            raise FalhaVetorizacao("Cloudflare recusou a requisição")
        resultado = payload.get("result", payload) if isinstance(payload, dict) else payload
        bruto = None
        if isinstance(resultado, dict):
            for chave in ("data", "response", "embeddings", "vectors"):
                if isinstance(resultado.get(chave), list):
                    bruto = resultado[chave]
                    break
        elif isinstance(resultado, list):
            bruto = resultado
        return _validar(bruto, self._dim, len(textos))


class HuggingFaceEmbedding:
    nome = "huggingface"

    def __init__(
        self, token: str, modelo: str, dim: int, timeout_s: float, cliente: httpx.Client | None = None
    ) -> None:
        self.modelo = modelo
        self._url = f"https://router.huggingface.co/hf-inference/models/{modelo}/pipeline/feature-extraction"
        self._token = token
        self._dim = dim
        self._cliente = cliente or httpx.Client(timeout=timeout_s)

    def vetorizar(self, textos: Sequence[str]) -> list[list[float]]:
        try:
            r = self._cliente.post(
                self._url,
                headers={"Authorization": f"Bearer {self._token}"},
                json={"inputs": list(textos), "normalize": True},
            )
        except httpx.HTTPError as e:
            raise FalhaVetorizacao(f"{type(e).__name__}: {e}") from e
        if r.status_code != 200:
            raise FalhaVetorizacao(f"HTTP {r.status_code}")
        try:
            dados = r.json()
        except ValueError as e:
            raise FalhaVetorizacao("resposta não é JSON") from e
        if isinstance(dados, dict):
            raise FalhaVetorizacao("Hugging Face devolveu erro")
        # Alguns modelos devolvem tokens x dim por texto: faz mean pooling.
        if dados and isinstance(dados[0], list) and dados[0] and isinstance(dados[0][0], list):
            dados = [[sum(col) / len(tok) for col in zip(*tok, strict=True)] for tok in dados]
        return _validar(dados, self._dim, len(textos))


@dataclass(frozen=True)
class Vetorizacao:
    vetor: list[float]
    provedor: str
    modelo: str
    latencia_ms: int


class CadeiaEmbeddings:
    """Tenta cada provedor na ordem; quem falha fica em cooldown."""

    def __init__(
        self,
        provedores: Sequence[Provedor],
        cooldown_s: float = 30.0,
        ao_falhar: Callable[[str], None] | None = None,
        *,
        cache_max: int = 0,
        cache_ttl_s: float = 3600.0,
        ao_acertar_cache: Callable[[], None] | None = None,
    ) -> None:
        self.provedores = list(provedores)
        self._cooldown = cooldown_s
        self._pausado_ate: dict[str, float] = {}
        self._ultima_latencia: dict[str, int] = {}
        self._trava = threading.Lock()
        self._ao_falhar = ao_falhar
        # Cache LRU de perguntas repetidas (só em vetorizar(), nunca no lote de documentos).
        # Mesmo texto -> mesmo vetor (o modelo é determinístico); poupa latência e cota.
        self._cache_max = cache_max
        self._cache_ttl = cache_ttl_s
        self._cache: OrderedDict[str, tuple[float, Vetorizacao]] = OrderedDict()
        self._ao_acertar_cache = ao_acertar_cache

    def _disponivel(self, p: Provedor) -> bool:
        with self._trava:
            return time.monotonic() >= self._pausado_ate.get(p.nome, 0.0)

    def vetorizar_lote(self, textos: Sequence[str]) -> tuple[list[list[float]], Provedor]:
        erros: list[str] = []
        candidatos = [p for p in self.provedores if self._disponivel(p)] or self.provedores
        for p in candidatos:
            inicio = time.perf_counter()
            try:
                vetores = p.vetorizar(textos)
            except FalhaVetorizacao as e:
                erros.append(f"{p.nome}: {e}")
                log.warning("falha de vetorização", extra={"provedor": p.nome, "motivo": str(e)})
                if self._ao_falhar:
                    self._ao_falhar(p.nome)
                with self._trava:
                    self._pausado_ate[p.nome] = time.monotonic() + self._cooldown
                continue
            with self._trava:
                self._pausado_ate.pop(p.nome, None)
                self._ultima_latencia[p.nome] = int((time.perf_counter() - inicio) * 1000)
            return vetores, p
        raise FalhaVetorizacao("; ".join(erros) or "nenhum provedor configurado")

    def vetorizar(self, texto: str) -> Vetorizacao:
        chave = " ".join(texto.lower().split())
        if self._cache_max:
            with self._trava:
                item = self._cache.get(chave)
                if item and time.monotonic() - item[0] < self._cache_ttl:
                    self._cache.move_to_end(chave)
                    if self._ao_acertar_cache:
                        self._ao_acertar_cache()
                    v = item[1]
                    return Vetorizacao(v.vetor, v.provedor, v.modelo, 0)
        inicio = time.perf_counter()
        vetores, p = self.vetorizar_lote([texto])
        resultado = Vetorizacao(vetores[0], p.nome, p.modelo, int((time.perf_counter() - inicio) * 1000))
        if self._cache_max:
            with self._trava:
                self._cache[chave] = (time.monotonic(), resultado)
                self._cache.move_to_end(chave)
                while len(self._cache) > self._cache_max:
                    self._cache.popitem(last=False)
        return resultado

    def estado(self) -> dict[str, Any]:
        """Para o /health: sem chamar a API (custa cota)."""
        if not self.provedores:
            return {"status": "falha", "latencia_ms": None}
        disponiveis = [p for p in self.provedores if self._disponivel(p)]
        if not disponiveis:
            return {"status": "falha", "latencia_ms": None}
        return {"status": "ok", "latencia_ms": self._ultima_latencia.get(disponiveis[0].nome)}
