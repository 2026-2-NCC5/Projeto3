"""Cache do índice lexical (fallback do RAG), reconstruído a cada N segundos ou quando a base muda."""

from __future__ import annotations

import logging
import threading
import time

from app.db.repositorio import ErroRepositorio, Repositorio
from app.rag.lexical import IndiceLexical

log = logging.getLogger("asa.rag.indice")


class CacheIndiceLexical:
    def __init__(self, repo: Repositorio, ttl_s: float) -> None:
        self._repo = repo
        self._ttl = ttl_s
        self._indice: IndiceLexical | None = None
        self._criado = 0.0
        self._trava = threading.Lock()

    def invalidar(self) -> None:
        with self._trava:
            self._criado = 0.0

    def obter(self) -> IndiceLexical | None:
        """Índice atual. Se o banco estiver fora, devolve o último construído (pode ser None)."""
        with self._trava:
            if self._indice is not None and time.monotonic() - self._criado < self._ttl:
                return self._indice
            try:
                chunks = self._repo.listar_chunks_ativos()
            except ErroRepositorio:
                log.warning("não foi possível atualizar o índice lexical; usando o anterior")
                return self._indice
            self._indice = IndiceLexical.construir(chunks)
            self._criado = time.monotonic()
            log.info("índice lexical construído", extra={"chunks": len(self._indice)})
            return self._indice
