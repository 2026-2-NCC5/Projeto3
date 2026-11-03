"""Avaliação do RAG: recuperação, abstenção, limiar e groundedness.

    ml/.venv/bin/python ml/avaliar_rag.py

Corpus: os 20 documentos fictícios da Entrega 1 (src/Entrega 1/seed_v2.sql).
Perguntas: ml/rag_eval/perguntas.jsonl (60: 20 diretas, 20 reformuladas,
8 de continuação, 12 fora do escopo).

Gera ml/artifacts/rag_metrics.json, ml/rag_eval/revisao_amostra.jsonl e
figuras docs/evidencias/rag_*.png.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

from rag.groundedness import verificar
from rag.recuperacao import (
    SEED_FICTICIO,
    EmbeddingDenso,
    Recuperador,
    TfidfHashing,
    carregar_corpus,
    montar_consulta,
)
from risco import graficos as g

PERGUNTAS = AQUI / "rag_eval" / "perguntas.jsonl"
SAIDA = AQUI / "artifacts" / "rag_metrics.json"
LIMIAR_PRODUCAO = 0.55  # web/api/perguntar.py (bge-m3)
SEMENTE = 42

METODOS = {
    "tfidf_hashing": ("TF-IDF (hashing, sem IDF)", lambda: TfidfHashing(usar_idf=False)),
    "tfidf_idf": ("TF-IDF + tabela IDF", lambda: TfidfHashing(usar_idf=True)),
    "minilm": ("MiniLM-L6 (all-MiniLM-L6-v2)", lambda: EmbeddingDenso("minilm", "sentence-transformers/all-MiniLM-L6-v2")),
    "minilm_multi": ("MiniLM-L12 multilíngue",
                     lambda: EmbeddingDenso("minilm_multi", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")),
    "bge_m3": ("bge-m3 (modelo de produção)", lambda: EmbeddingDenso("bge_m3", "BAAI/bge-m3")),
}
DENTRO = {"direta", "reformulada", "continuacao"}


def carregar_perguntas() -> list[dict[str, Any]]:
    return [json.loads(linha) for linha in PERGUNTAS.read_text(encoding="utf-8").splitlines() if linha.strip()]


def _r(x: float) -> float:
    return round(float(x), 4)


# ---------------------------------------------------------------------------
# Execução de um método
# ---------------------------------------------------------------------------

def rodar(rec: Recuperador, perguntas: list[dict[str, Any]], janela: int = 1) -> list[dict[str, Any]]:
    consultas = [montar_consulta(p["pergunta"], p["contexto"], janela) for p in perguntas]
    Q = rec.v.vetorizar(consultas, consulta=True)
    sims = Q @ rec.E.T
    docs = np.array([c.documento_id for c in rec.chunks])
    out = []
    for p, s in zip(perguntas, sims):
        ordem = np.argsort(-s)
        ranking = list(dict.fromkeys(docs[ordem]))           # documentos em ordem, sem repetição
        esperados = set(p["documentos_esperados"])
        rank = next((i + 1 for i, d in enumerate(ranking) if d in esperados), None) if esperados else None
        out.append({"id": p["id"], "tipo": p["tipo"], "dentro": p["tipo"] in DENTRO, "sim_top1": float(s[ordem[0]]),
                    "doc_top1": ranking[0], "rank": rank, "top1_correto": rank == 1,
                    "top3_ids": [rec.chunks[i].chunk_id for i in ordem[:3]]})
    return out


def metricas_recuperacao(res: list[dict[str, Any]]) -> dict[str, Any]:
    dentro = [r for r in res if r["dentro"]]
    def agg(rs: list[dict[str, Any]]) -> dict[str, float]:
        return {"n": len(rs), "recall_at_1": _r(np.mean([r["rank"] == 1 for r in rs])),
                "recall_at_3": _r(np.mean([r["rank"] is not None and r["rank"] <= 3 for r in rs])),
                "mrr": _r(np.mean([1 / r["rank"] for r in rs]))}
    por_tipo = {t: agg([r for r in dentro if r["tipo"] == t]) for t in ("direta", "reformulada", "continuacao")}
    return {"dentro_do_escopo": agg(dentro), "por_tipo": por_tipo}


def decisao(res: list[dict[str, Any]], t: float) -> dict[str, float]:
    """Comportamento do agente com limiar t (abstém se similaridade top-1 < t)."""
    dentro = [r for r in res if r["dentro"]]
    fora = [r for r in res if not r["dentro"]]
    responde = lambda r: r["sim_top1"] >= t
    respondidas = [r for r in res if responde(r)]
    certas = sum(responde(r) and r["top1_correto"] for r in dentro) + sum(not responde(r) for r in fora)
    return {
        "limiar": _r(t),
        "abstencao_correta": _r(np.mean([not responde(r) for r in fora])) if fora else None,
        "abstencao_indevida": _r(np.mean([not responde(r) for r in dentro])),
        "precisao_das_respostas": _r(np.mean([r["dentro"] and r["top1_correto"] for r in respondidas])) if respondidas else None,
        "respostas_erradas": int(sum(not (r["dentro"] and r["top1_correto"]) for r in respondidas)),
        "acerto_do_agente": _r(certas / len(res)),
    }


def limiar_otimo(res: list[dict[str, Any]]) -> float:
    """Maximiza o acerto do agente.

    Os limiares ótimos podem formar vários intervalos separados. Fica o intervalo
    contíguo de MAIOR limiar (mais conservador: abstenção é resposta válida), e
    dentro dele o ponto médio, que é o mais distante das perguntas vizinhas.
    """
    s = np.unique([r["sim_top1"] for r in res])
    candidatos = np.r_[s[0] - 1e-3, (s[:-1] + s[1:]) / 2, s[-1] + 1e-3]
    acertos = np.array([decisao(res, t)["acerto_do_agente"] for t in candidatos])
    otimo = np.flatnonzero(acertos == acertos.max())
    fim = otimo[-1]
    inicio = fim
    while inicio - 1 in set(otimo.tolist()):
        inicio -= 1
    return float((candidatos[inicio] + candidatos[fim]) / 2)


def acerto_cv(res: list[dict[str, Any]], k: int = 5) -> dict[str, float]:
    """Estimativa honesta: limiar escolhido em k-1 partes e medido na parte restante."""
    rng = np.random.default_rng(SEMENTE)
    idx_d = rng.permutation([i for i, r in enumerate(res) if r["dentro"]])
    idx_f = rng.permutation([i for i, r in enumerate(res) if not r["dentro"]])
    dobras = [np.r_[idx_d[j::k], idx_f[j::k]] for j in range(k)]
    acertos, limiares = [], []
    for j in range(k):
        teste = set(dobras[j].tolist())
        tr = [r for i, r in enumerate(res) if i not in teste]
        te = [r for i, r in enumerate(res) if i in teste]
        t = limiar_otimo(tr)
        limiares.append(t)
        acertos.append(decisao(te, t)["acerto_do_agente"] * len(te))
    return {"acerto_cv": _r(sum(acertos) / len(res)), "limiar_medio": _r(np.mean(limiares)), "limiar_dp": _r(np.std(limiares))}


# ---------------------------------------------------------------------------
# Groundedness
# ---------------------------------------------------------------------------

def _trocar_numero(texto: str) -> str | None:
    m = re.search(r"\d+", texto)
    if not m:
        return None
    n = int(m.group())
    novo = str(n + 7 if n < 50 else n * 2)
    return texto[:m.start()] + novo + texto[m.end():]


INVENTADAS = [
    "Além disso, o pedido também pode ser feito pelo WhatsApp da coordenação.",
    "Em caso de atraso, é cobrada uma multa de 2% sobre o valor da mensalidade.",
    "Alunos do último semestre estão isentos dessa exigência.",
]


def validar_verificador(chunks) -> dict[str, Any]:
    """Respostas adulteradas devem ser pegas; respostas fiéis não podem ser acusadas."""
    fieis, numero, inventada = [], [], []
    for i, c in enumerate(chunks):
        fieis.append(verificar(c.conteudo, [c.conteudo])["fundamentada"])
        primeira = re.split(r"(?<=[.!?])\s+", c.conteudo)[0]
        fieis.append(verificar(primeira, [c.conteudo])["fundamentada"])           # resumo extrativo
        t = _trocar_numero(c.conteudo)
        if t:
            numero.append(not verificar(t, [c.conteudo])["fundamentada"])
        inventada.append(not verificar(c.conteudo + " " + INVENTADAS[i % 3], [c.conteudo])["fundamentada"])
    return {
        "respostas_fieis_aceitas": _r(np.mean(fieis)), "n_fieis": len(fieis),
        "numero_trocado_detectado": _r(np.mean(numero)), "n_numero": len(numero),
        "frase_inventada_detectada": _r(np.mean(inventada)), "n_inventada": len(inventada),
    }


def groundedness_respostas(rec: Recuperador, perguntas: list[dict[str, Any]], res: list[dict[str, Any]],
                           t: float) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    por_id = {c.chunk_id: c for c in rec.chunks}
    titulo = {c.documento_id: c.titulo_documento for c in rec.chunks}
    linhas = []
    for p, r in zip(perguntas, res):
        if r["sim_top1"] < t:
            continue
        trechos = [por_id[cid].conteudo for cid in r["top3_ids"]]
        resp = rec.processar_pergunta(p["pergunta"], p["contexto"], limiar=t)
        v = verificar(resp["resposta"], trechos)
        linhas.append({"id": p["id"], "tipo": p["tipo"], "pergunta": p["pergunta"], "contexto": p["contexto"],
                       "resposta": resp["resposta"], "documento_recuperado": titulo[r["doc_top1"]],
                       "documentos_esperados": [titulo[d] for d in p["documentos_esperados"]],
                       "doc_correto": r["top1_correto"], "groundedness": v["score"]})
    n = len(linhas) or 1
    return {
        "respostas_avaliadas": len(linhas),
        "groundedness_media": _r(sum(x["groundedness"] for x in linhas) / n),
        "respostas_100pct_fundamentadas": _r(sum(x["groundedness"] == 1 for x in linhas) / n),
        "fundamentadas_mas_documento_errado": int(sum(not x["doc_correto"] for x in linhas)),
    }, linhas


# ---------------------------------------------------------------------------
# Figuras
# ---------------------------------------------------------------------------

def fig_recuperacao(M: dict[str, Any]) -> None:
    nomes = list(M)
    x = np.arange(len(nomes))
    fig, ax = plt.subplots(figsize=(9, 4.4))
    for i, (k, rot) in enumerate((("recall_at_1", "Recall@1"), ("recall_at_3", "Recall@3"), ("mrr", "MRR"))):
        v = [M[n]["recuperacao"]["dentro_do_escopo"][k] for n in nomes]
        ax.bar(x + (i - 1) * 0.26, v, 0.24, color=g.SERIE[i], label=rot)
        for xi, vi in zip(x, v):
            ax.text(xi + (i - 1) * 0.26, vi + 0.01, f"{vi:.2f}", ha="center", fontsize=7.5, color=g.TEXTO_2)
    ax.set_xticks(x, [M[n]["nome"].replace(" (", "\n(") for n in nomes], fontsize=8.5)
    ax.set(ylim=(0, 1.1), title="Recuperação nas 48 perguntas dentro do escopo")
    ax.legend(loc="upper left", ncol=3)
    ax.grid(axis="x", visible=False)
    g.salvar(fig, "rag_recuperacao.png"); plt.close(fig)


def fig_similaridades(M: dict[str, Any], R: dict[str, list[dict[str, Any]]]) -> None:
    nomes = list(M)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    rng = np.random.default_rng(0)
    for i, n in enumerate(nomes):
        for dentro, cor, dx in ((True, g.SERIE[0], -0.15), (False, g.SERIE[1], 0.15)):
            s = [r["sim_top1"] for r in R[n] if r["dentro"] == dentro]
            ax.scatter(np.full(len(s), i + dx) + rng.uniform(-0.06, 0.06, len(s)), s, s=14, color=cor, alpha=0.75,
                       linewidths=0, label=("Dentro do escopo" if dentro else "Fora do escopo") if i == 0 else None)
        t = M[n]["limiar_otimo"]
        ax.plot([i - 0.32, i + 0.32], [t, t], color=g.TEXTO, lw=1.6, label="Limiar ótimo" if i == 0 else None)
    ax.set_xticks(range(len(nomes)), [M[n]["nome"].replace(" (", "\n(") for n in nomes], fontsize=8.5)
    ax.set(ylabel="Similaridade do trecho top-1", title="Separação entre perguntas dentro e fora do escopo")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(axis="x", visible=False)
    g.salvar(fig, "rag_similaridades.png"); plt.close(fig)


def fig_limiar(res: list[dict[str, Any]], nome: str, t_otimo: float, t_prod: float | None) -> None:
    s = sorted(r["sim_top1"] for r in res)
    ts = np.linspace(min(s) - 0.02, max(s) + 0.02, 200)
    d = [decisao(res, t) for t in ts]
    fig, ax = plt.subplots(figsize=(7.5, 4.3))
    ax.plot(ts, [x["abstencao_correta"] * 100 for x in d], color=g.SERIE[0], label="Abstenção correta (fora do escopo)")
    ax.plot(ts, [x["abstencao_indevida"] * 100 for x in d], color=g.SERIE[1], label="Abstenção indevida (dentro)")
    ax.plot(ts, [x["acerto_do_agente"] * 100 for x in d], color=g.SERIE[2], label="Acerto do agente")
    ax.axvline(t_otimo, color=g.TEXTO, lw=1, ls="--")
    ax.text(t_otimo - 0.005, 92, f"ótimo {t_otimo:.3f}", ha="right", fontsize=8, color=g.TEXTO)
    if t_prod is not None:
        ax.axvline(t_prod, color=g.TEXTO_2, lw=1, ls=":")
        ax.text(t_prod, -9, f"produção {t_prod:.2f}", ha="center", fontsize=8, color=g.TEXTO_2)
    ax.set(xlabel="Limiar de similaridade", ylabel="%", title=f"Escolha do limiar · {nome}", ylim=(-12, 108))
    ax.legend(loc="center left", fontsize=8)
    g.salvar(fig, "rag_limiar.png"); plt.close(fig)


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------

def executar(metodos: list[str] | None = None, verbose: bool = True) -> dict[str, Any]:
    log = print if verbose else (lambda *a, **k: None)
    perguntas = carregar_perguntas()
    chunks = carregar_corpus()
    M: dict[str, Any] = {}
    R: dict[str, list[dict[str, Any]]] = {}
    recs: dict[str, Recuperador] = {}
    for chave in metodos or list(METODOS):
        nome, fabrica = METODOS[chave]
        rec = Recuperador(fabrica(), chunks)
        res = rodar(rec, perguntas)
        sem_ctx = rodar(rec, [p for p in perguntas if p["tipo"] == "continuacao"], janela=0)
        t = limiar_otimo(res)
        recs[chave], R[chave] = rec, res
        M[chave] = {
            "nome": nome,
            "recuperacao": metricas_recuperacao(res),
            "continuacao_sem_contexto_recall_at_1": _r(np.mean([r["rank"] == 1 for r in sem_ctx])),
            "similaridade_top1": {
                "dentro_media": _r(np.mean([r["sim_top1"] for r in res if r["dentro"]])),
                "dentro_min": _r(min(r["sim_top1"] for r in res if r["dentro"])),
                "fora_media": _r(np.mean([r["sim_top1"] for r in res if not r["dentro"]])),
                "fora_max": _r(max(r["sim_top1"] for r in res if not r["dentro"])),
            },
            "limiar_otimo": _r(t),
            "no_limiar_otimo": decisao(res, t),
            "validacao_cruzada_limiar": acerto_cv(res),
        }
        if chave == "bge_m3":
            M[chave]["no_limiar_producao_0_55"] = decisao(res, LIMIAR_PRODUCAO)
        rr = M[chave]["recuperacao"]["dentro_do_escopo"]
        log(f"[{chave}] R@1 {rr['recall_at_1']} R@3 {rr['recall_at_3']} MRR {rr['mrr']} | limiar {t:.3f} "
            f"{M[chave]['no_limiar_otimo']} | CV {M[chave]['validacao_cruzada_limiar']}")

    # Escolha: maior acerto estimado por CV; empate -> maior MRR
    melhor = max(M, key=lambda k: (M[k]["validacao_cruzada_limiar"]["acerto_cv"], M[k]["recuperacao"]["dentro_do_escopo"]["mrr"]))
    gr, linhas = groundedness_respostas(recs[melhor], perguntas, R[melhor], M[melhor]["limiar_otimo"])
    valid = validar_verificador(chunks)
    amostra = [linhas[i] for i in np.random.default_rng(SEMENTE).choice(len(linhas), size=min(12, len(linhas)), replace=False)]
    erradas = [x for x in linhas if not x["doc_correto"]]
    arq_rev = AQUI / "rag_eval" / "revisao_amostra.jsonl"
    anteriores = {}
    if arq_rev.exists():  # preserva a revisão manual se a resposta não mudou
        for linha in arq_rev.read_text(encoding="utf-8").splitlines():
            x = json.loads(linha)
            anteriores[x["id"]] = (x["resposta"], x.get("revisao_humana"))
    sel = sorted(amostra + [e for e in erradas if e not in amostra], key=lambda x: x["id"])
    for x in sel:
        resp, rev = anteriores.get(x["id"], (None, None))
        x["revisao_humana"] = rev if resp == x["resposta"] else None
    arq_rev.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in sel), encoding="utf-8")
    revisadas = [x["revisao_humana"] for x in sel if x["revisao_humana"]]
    resumo_rev = {
        "arquivo": "ml/rag_eval/revisao_amostra.jsonl", "n": len(sel), "revisadas": len(revisadas),
        "responde_a_pergunta": _r(np.mean([r["responde_a_pergunta"] for r in revisadas])) if revisadas else None,
        "fundamentada": _r(np.mean([r["fundamentada"] for r in revisadas])) if revisadas else None,
        "revisor": revisadas[0]["revisor"] if revisadas else None,
    }

    fig_recuperacao(M)
    fig_similaridades(M, R)
    fig_limiar(R[melhor], M[melhor]["nome"], M[melhor]["limiar_otimo"], LIMIAR_PRODUCAO if melhor == "bge_m3" else None)

    saida = {
        "gerado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        "corpus": {"fonte": str(SEED_FICTICIO.relative_to(SEED_FICTICIO.parents[2])), "documentos": len({c.documento_id for c in chunks}),
                   "chunks": len(chunks), "observacao": "documentos fictícios da Entrega 1; a base real (230 documentos) não foi usada aqui"},
        "perguntas": {"total": len(perguntas), "por_tipo": {t: sum(p["tipo"] == t for p in perguntas)
                                                           for t in dict.fromkeys(p["tipo"] for p in perguntas)}},
        "definicoes": {
            "recall_at_k": "fração das perguntas dentro do escopo com um documento esperado entre os k primeiros",
            "mrr": "média de 1/posição do primeiro documento esperado no ranking completo",
            "abstencao_correta": "fração das perguntas fora do escopo em que o agente se absteve",
            "abstencao_indevida": "fração das perguntas dentro do escopo em que o agente se absteve",
            "acerto_do_agente": "(dentro: respondeu com o documento certo no top-1) + (fora: absteve-se), sobre o total",
            "acerto_cv": "limiar escolhido em 4/5 das perguntas e medido no 1/5 restante (5 dobras)",
            "contexto": "continuações usam a última pergunta do estudante concatenada à atual",
        },
        "metodos": M,
        "escolhido": {"metodo": melhor, "nome": M[melhor]["nome"], "limiar": M[melhor]["limiar_otimo"]},
        "groundedness": {**gr, "metodo": melhor,
                         "observacao": "a resposta atual é extrativa (trecho top-1), por isso é sempre fundamentada; "
                                       "o risco real é responder com o trecho de outro documento"},
        "validacao_verificador_groundedness": valid,
        "revisao_amostra": resumo_rev,
    }
    SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=2))
    log(f"Escolhido: {melhor} · limiar {M[melhor]['limiar_otimo']:.3f} · groundedness {gr} · verificador {valid}")
    return saida


if __name__ == "__main__":
    executar()
