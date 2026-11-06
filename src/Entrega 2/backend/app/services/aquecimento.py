"""Warm-up ao iniciar: evita que a primeira pergunta da apresentação seja a lenta.

Monta o índice lexical (lê todos os trechos ativos), faz uma busca nele e, se
houver provedor de embedding, vetoriza uma pergunta comum (abre a conexão TLS e
deixa o vetor no cache). Não grava nada no banco nem na auditoria.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

log = logging.getLogger("asa.aquecimento")

PERGUNTA_AQUECIMENTO = "Como faço para trancar a matrícula?"


def aquecer(estado: Any) -> None:
    inicio = time.perf_counter()
    try:
        indice = estado.indice_lexical.obter()
        if indice is not None:
            indice.buscar(PERGUNTA_AQUECIMENTO, 3)
        if estado.embeddings.provedores:
            estado.embeddings.vetorizar(PERGUNTA_AQUECIMENTO)
    except Exception:
        log.warning("warm-up incompleto", exc_info=True)
        return
    log.info("warm-up concluído", extra={"latencia_ms": int((time.perf_counter() - inicio) * 1000)})


def aquecer_em_segundo_plano(estado: Any) -> None:
    threading.Thread(target=aquecer, args=(estado,), name="aquecimento", daemon=True).start()
