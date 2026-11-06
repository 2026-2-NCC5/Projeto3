"""Avaliação do modelo de risco v2 no conjunto de teste (split da Entrega 1).

    ASA_DATA_DIR=/caminho/para/data python ml/avaliar.py

Lê ml/artifacts/risco_v2.joblib (+ candidatos.joblib, local) e gera:
  - figuras PNG em docs/evidencias/
  - seção "avaliacao" de ml/artifacts/metrics.json
  - ml/artifacts/MODEL_VERSION.json
  - atualiza as métricas embutidas no artefato (servidas em /risco/modelo)

Só números agregados saem daqui. Subgrupos com menos de 30 alunos no teste
são suprimidos.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

from risco import dados
from risco import graficos as g
from risco.modelo import CATALOGO, NUNCA_COMO_FATOR, RiskModel, normalizar_entrada

ARTIFACTS = AQUI / "artifacts"
MIN_GRUPO = 30
CAPACIDADES = [0.05, 0.10, 0.15, 0.20, 0.30, 0.40]
ROTULO = {"verde": "Verde", "amarelo": "Amarelo", "vermelho": "Vermelho"}


def _r(x: float, n: int = 4) -> float:
    return round(float(x), n)


def metricas_limiar(y: np.ndarray, p: np.ndarray, limiar: float) -> dict[str, float]:
    pred = (p >= limiar).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred).ravel()
    return {
        "limiar": _r(limiar), "auc": _r(roc_auc_score(y, p)), "pr_auc": _r(average_precision_score(y, p)),
        "brier": _r(brier_score_loss(y, p)), "recall": _r(recall_score(y, pred)),
        "precisao": _r(precision_score(y, pred, zero_division=0)), "f1": _r(f1_score(y, pred)),
        "pct_sinalizados": _r(pred.mean()), "matriz_confusao": {"vn": int(tn), "fp": int(fp), "fn": int(fn), "vp": int(tp)},
    }


def faixas(y: np.ndarray, p: np.ndarray, lim: dict[str, float]) -> dict[str, Any]:
    cat = np.where(p >= lim["vermelho"], "vermelho", np.where(p >= lim["amarelo"], "amarelo", "verde"))
    out = {}
    for c in ("verde", "amarelo", "vermelho"):
        m = cat == c
        out[c] = {"n": int(m.sum()), "pct_alunos": _r(m.mean()),
                  "taxa_evasao_real": _r(y[m].mean()) if m.any() else None,
                  "prob_media_prevista": _r(p[m].mean()) if m.any() else None}
    taxas = [out[c]["taxa_evasao_real"] or 0 for c in ("verde", "amarelo", "vermelho")]
    out["monotonica"] = bool(taxas[0] < taxas[1] < taxas[2])
    return out


def capacidade(y: np.ndarray, p: np.ndarray) -> tuple[list[dict[str, float]], pd.DataFrame]:
    ordem = np.argsort(-p)
    ys = y[ordem]
    n, pos = len(y), y.sum()
    k = np.arange(1, n + 1)
    curva = pd.DataFrame({"pct_contatados": k / n, "recall": np.cumsum(ys) / pos,
                          "precisao": np.cumsum(ys) / k, "limiar": p[ordem]})
    tabela = []
    for c in CAPACIDADES:
        i = int(np.ceil(c * n)) - 1
        tabela.append({"pct_contatados": c, "n_contatados": i + 1, "limiar_equivalente": _r(curva.limiar[i]),
                       "recall": _r(curva.recall[i]), "precisao": _r(curva.precisao[i]),
                       "lift": _r(curva.precisao[i] / (pos / n), 2)})
    return tabela, curva


def metricas_grupo(y: np.ndarray, sinal: np.ndarray, grupos: pd.DataFrame) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for col in grupos.columns:
        out[col] = {}
        for val, idx in grupos.groupby(col).groups.items():
            m = grupos.index.isin(idx)
            if m.sum() < MIN_GRUPO:
                out[col][str(val)] = {"n": "<30 (suprimido)"}
                continue
            yy, ss = y[m], sinal[m]
            out[col][str(val)] = {
                "n": int(m.sum()), "taxa_evasao_real": _r(yy.mean()), "taxa_sinalizacao": _r(ss.mean()),
                "recall": _r(ss[yy == 1].mean()) if (yy == 1).sum() >= 5 else None,
                "taxa_falsos_positivos": _r(ss[yy == 0].mean()) if (yy == 0).sum() >= 5 else None,
                "precisao": _r(yy[ss == 1].mean()) if ss.sum() >= 5 else None,
            }
    return out


def lacunas(por_grupo: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Maior diferença entre valores de cada atributo (recall e FPR), só grupos válidos."""
    out = {}
    for col, vals in por_grupo.items():
        ok = [v for v in vals.values() if isinstance(v.get("n"), int)]
        res = {}
        for k in ("recall", "taxa_falsos_positivos", "taxa_sinalizacao"):
            xs = [v[k] for v in ok if v.get(k) is not None]
            if len(xs) >= 2:
                res[k] = _r(max(xs) - min(xs))
        out[col] = res
    return out


def perfil_erros(df: pd.DataFrame, y: np.ndarray, sinal: np.ndarray, contrib: pd.DataFrame) -> dict[str, Any]:
    tipo = np.select([(y == 1) & (sinal == 1), (y == 1) & (sinal == 0), (y == 0) & (sinal == 1)],
                     ["VP", "FN", "FP"], "VN")
    num = ["media_notas", "media_assiduidade", "pct_reprovacao", "pct_parcelas_em_aberto", "atraso_medio_dias",
           "total_parcelas", "valor_total_periodo", "tempo_de_curso", "total_semestres", "tendencia_assiduidade", "Idade"]
    d = df[num].copy()
    d["tipo"] = tipo
    med = d.groupby("tipo")[num].median().round(2)
    sem_notas = d.assign(sem=(df["media_notas"] == 0) & (df["media_assiduidade"] == 0)).groupby("tipo")["sem"].mean().round(3)
    cats = {}
    for c in ["Grau Acadêmico", "Turno", "Forma de Ingresso"]:
        t = pd.crosstab(tipo, df[c], normalize="index").round(3)
        cats[c] = {k: {kk: float(vv) for kk, vv in row.items()} for k, row in t.iterrows()}
    dom = contrib.abs().idxmax(axis=1).map(lambda c: CATALOGO[c].dimensao if c in CATALOGO else "perfil")
    dim = pd.crosstab(tipo, dom, normalize="index").round(3)
    return {
        "n": {k: int((tipo == k).sum()) for k in ("VP", "FN", "FP", "VN")},
        "medianas": {k: {kk: float(vv) for kk, vv in row.items()} for k, row in med.iterrows()},
        "pct_sem_notas_e_frequencia": {k: float(v) for k, v in sem_notas.items()},
        "categorias": cats,
        "dimensao_do_fator_dominante": {k: {kk: float(vv) for kk, vv in row.items()} for k, row in dim.iterrows()},
    }


def _mil(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


def observacoes_erros(pe: dict[str, Any], por_grupo: dict[str, Any]) -> list[str]:
    """Observações geradas a partir dos números (nada aqui é afirmado sem o valor ao lado)."""
    m, sn, cat = pe["medianas"], pe["pct_sem_notas_e_frequencia"], pe["categorias"]
    grau = por_grupo.get("Grau Acadêmico", {})
    rec = {k: v.get("recall") for k, v in grau.items() if isinstance(v.get("n"), int)}
    pos_fn = cat["Grau Acadêmico"].get("FN", {}).get("Pós-Graduação", 0)
    return [
        f"Falsos negativos (evadiram sem ser sinalizados) parecem alunos que ficam: nota mediana {m['FN']['media_notas']:.0f} "
        f"(VN {m['VN']['media_notas']:.0f}), frequência {m['FN']['media_assiduidade']:.0f}% (VN {m['VN']['media_assiduidade']:.0f}%), "
        f"{m['FN']['total_semestres']:.0f} semestres cursados (VN {m['VN']['total_semestres']:.0f}). É a evasão de quem estava "
        "bem: os dados disponíveis não têm sinal para ela.",
        f"Falsos positivos parecem os verdadeiros positivos: {sn.get('FP', 0):.0%} deles não têm nenhuma nota nem frequência "
        f"lançadas (VP {sn.get('VP', 0):.0%}, VN {sn.get('VN', 0):.0%}), tempo de curso mediano {m['FP']['tempo_de_curso']:.0f} "
        f"e valor do período mediano R$ {_mil(m['FP']['valor_total_periodo'])} (VP R$ {_mil(m['VP']['valor_total_periodo'])}, "
        f"VN R$ {_mil(m['VN']['valor_total_periodo'])}). São sobretudo ingressantes sem histórico; para eles, um contato de "
        "acolhimento tem custo baixo e não é perdido.",
        f"Pós-Graduação responde por {pos_fn:.0%} dos falsos negativos. Recall por grau: "
        + ", ".join(f"{k} {v:.0%}" for k, v in rec.items() if v is not None)
        + ". Onde o recall é menor, vale uma rotina própria (ex.: contato no 1º mês), independente do score.",
        f"Veteranos escapam mais: os FN têm mediana de {m['FN']['total_parcelas']:.0f} parcelas contra "
        f"{m['VP']['total_parcelas']:.0f} dos VP. Recalcular o score todo mês, com notas e frequência do mês corrente, "
        "é o caminho para pegar quem piora no meio do curso.",
        "A base é um retrato tirado depois do desfecho: quem evadiu tem mediana 0 de parcelas em aberto (as parcelas são "
        f"encerradas) e {sn.get('VP', 0):.0%} dos VP não têm notas lançadas. Isso infla a AUC e foi o motivo das restrições "
        "monotônicas. Antes de confiar no número absoluto, a v3 precisa de features com data de corte anterior à evasão.",
    ]


# ---------------------------------------------------------------------------
# Figuras
# ---------------------------------------------------------------------------

def fig_curvas(y: np.ndarray, probs: dict[str, np.ndarray]) -> None:
    fig, ax = plt.subplots(figsize=(6, 5))
    for alg, p in probs.items():
        fpr, tpr, _ = roc_curve(y, p)
        ax.plot(fpr, tpr, color=g.COR_MODELO[alg], label=f"{g.NOME_MODELO[alg]} · AUC {roc_auc_score(y, p):.3f}")
    ax.plot([0, 1], [0, 1], color=g.TEXTO_2, lw=1, ls="--", label="Acaso")
    ax.set(xlabel="Taxa de falsos positivos", ylabel="Recall (taxa de verdadeiros positivos)",
           title="Curva ROC no conjunto de teste (modelos calibrados)")
    ax.legend(loc="lower right")
    g.salvar(fig, "risco_roc_modelos.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 5))
    for alg, p in probs.items():
        pr, rc, _ = precision_recall_curve(y, p)
        ax.plot(rc, pr, color=g.COR_MODELO[alg], label=f"{g.NOME_MODELO[alg]} · PR-AUC {average_precision_score(y, p):.3f}")
    ax.axhline(y.mean(), color=g.TEXTO_2, lw=1, ls="--", label=f"Taxa de evasão ({y.mean():.0%})")
    ax.set(xlabel="Recall", ylabel="Precisão", title="Curva Precisão × Recall no teste", ylim=(0, 1.02))
    ax.legend(loc="lower left")
    g.salvar(fig, "risco_pr_modelos.png"); plt.close(fig)


def fig_matriz(mc: dict[str, int], titulo: str, nome: str) -> None:
    m = np.array([[mc["vn"], mc["fp"]], [mc["fn"], mc["vp"]]])
    fig, ax = plt.subplots(figsize=(4.6, 4))
    ax.imshow(m, cmap="Blues", vmin=0)
    ax.grid(False)
    for (i, j), v in np.ndenumerate(m):
        ax.text(j, i, f"{v}\n({v / m.sum():.1%})", ha="center", va="center",
                color="#ffffff" if v > m.max() * 0.55 else g.TEXTO, fontsize=10)
    ax.set_xticks([0, 1], ["Verde (não sinalizado)", "Amarelo/Vermelho"])
    ax.set_yticks([0, 1], ["Não evadiu", "Evadiu"])
    ax.set(xlabel="Previsão", ylabel="Real", title=titulo)
    g.salvar(fig, nome); plt.close(fig)


def fig_capacidade(curva: pd.DataFrame, tabela: list[dict[str, float]], pct_e1: float, recall_e1: float) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(curva.pct_contatados * 100, curva.recall * 100, color=g.SERIE[0], label="Recall (evasões alcançadas)")
    ax.plot(curva.pct_contatados * 100, curva.precisao * 100, color=g.SERIE[1], label="Precisão (contatos que eram evasão)")
    for t in tabela:
        if t["pct_contatados"] in (0.05, 0.10, 0.20):
            x, yv = t["pct_contatados"] * 100, t["recall"] * 100
            ax.plot([x], [yv], "o", color=g.SERIE[0], ms=7, mec=g.SUPERFICIE, mew=2)
            ax.annotate(f"{yv:.0f}%", (x, yv), xytext=(6, -14), textcoords="offset points", fontsize=9, color=g.TEXTO)
    ax.plot([pct_e1 * 100], [recall_e1 * 100], "s", color=g.TEXTO_2, ms=7, label="Baseline E1 (RL, corte 0,5)")
    ax.set(xlabel="Alunos contatados (% da base, do maior para o menor risco)", ylabel="%",
           title="Carga de atendimento × Recall × Precisão", xlim=(0, 60), ylim=(0, 102))
    ax.legend(loc="lower right")
    g.salvar(fig, "risco_capacidade.png"); plt.close(fig)


def fig_faixas(fx: dict[str, dict[str, Any]]) -> None:
    fig, axes = plt.subplots(1, len(fx), figsize=(5.2 * len(fx), 4.2), sharey=True)
    for ax, (nome, f) in zip(np.atleast_1d(axes), fx.items()):
        cs = ["verde", "amarelo", "vermelho"]
        x = np.arange(3)
        ax.bar(x - 0.2, [f[c]["pct_alunos"] * 100 for c in cs], 0.38, color=[g.RISCO[c] for c in cs], alpha=0.35,
               label="% dos alunos")
        ax.bar(x + 0.2, [(f[c]["taxa_evasao_real"] or 0) * 100 for c in cs], 0.38, color=[g.RISCO[c] for c in cs],
               label="Taxa real de evasão")
        for i, c in enumerate(cs):
            ax.text(i - 0.2, f[c]["pct_alunos"] * 100 + 1.5, f"{f[c]['pct_alunos']:.0%}", ha="center", fontsize=9, color=g.TEXTO_2)
            ax.text(i + 0.2, (f[c]["taxa_evasao_real"] or 0) * 100 + 1.5, f"{(f[c]['taxa_evasao_real'] or 0):.0%}",
                    ha="center", fontsize=9, color=g.TEXTO, weight="bold")
        ax.set_xticks(x, [ROTULO[c] for c in cs])
        ax.set_title(nome, fontsize=11)
        ax.grid(axis="x", visible=False)
    np.atleast_1d(axes)[0].set_ylabel("%")
    fig.legend(loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.04), handles=[
        plt.Rectangle((0, 0), 1, 1, color=g.TEXTO_2, alpha=0.35), plt.Rectangle((0, 0), 1, 1, color=g.TEXTO_2)],
        labels=["% dos alunos na faixa (claro)", "Taxa real de evasão (escuro)"])
    fig.suptitle("Faixas de risco no teste: tamanho e evasão real", x=0.01, ha="left", fontsize=12, weight="bold")
    g.salvar(fig, "risco_faixas.png"); plt.close(fig)


def fig_calibracao(y: np.ndarray, p_sem: np.ndarray, p_cal: np.ndarray, metodo: str) -> dict[str, Any]:
    fig, ax = plt.subplots(figsize=(5.5, 5))
    out = {}
    for nome, p, cor in (("Sem calibrar (pesos balanceados)", p_sem, g.SERIE[1]), (f"Calibrado ({metodo})", p_cal, g.SERIE[0])):
        fr, mp = calibration_curve(y, p, n_bins=10, strategy="quantile")
        ax.plot(mp, fr, "o-", color=cor, ms=5, label=f"{nome} · Brier {brier_score_loss(y, p):.3f}")
        out[nome] = {"brier": _r(brier_score_loss(y, p)), "ece": _r(np.mean(np.abs(fr - mp))),
                     "curva": [{"prevista": _r(a), "observada": _r(b)} for a, b in zip(mp, fr)]}
    ax.plot([0, 1], [0, 1], color=g.TEXTO_2, lw=1, ls="--", label="Calibração perfeita")
    ax.set(xlabel="Probabilidade prevista (média do decil)", ylabel="Evasão observada", title="Curva de calibração no teste")
    ax.legend(loc="upper left")
    g.salvar(fig, "risco_calibracao.png"); plt.close(fig)
    return out


def fig_importancia(contrib: pd.DataFrame, perm: pd.Series) -> None:
    imp = contrib.abs().mean().sort_values()
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.2))
    rot = [c.replace("_", " ") for c in imp.index]
    axes[0].barh(rot, imp.values, color=g.SERIE[0], height=0.6)
    axes[0].set(title="Contribuição média |SHAP| (log-odds)", xlabel="média |contribuição|")
    axes[0].grid(axis="y", visible=False)
    p = perm.reindex(imp.index)
    axes[1].barh(rot, p.values, color=g.SERIE[2], height=0.6)
    axes[1].set(title="Importância por permutação (queda de AUC)", xlabel="queda média de AUC")
    axes[1].grid(axis="y", visible=False)
    g.salvar(fig, "risco_importancia_global.png"); plt.close(fig)

    # direção: média da contribuição quando o atributo empurra para cima vs para baixo
    top = imp.index[::-1][:10]
    fig, ax = plt.subplots(figsize=(7, 4.8))
    up = contrib[top].clip(lower=0).mean()
    dn = contrib[top].clip(upper=0).mean()
    yy = np.arange(len(top))[::-1]
    ax.barh(yy, up.values, color=g.AUMENTA, height=0.6, label="Aumenta o risco")
    ax.barh(yy, dn.values, color=g.REDUZ, height=0.6, label="Reduz o risco")
    ax.set_yticks(yy, [c.replace("_", " ") for c in top])
    ax.axvline(0, color=g.TEXTO_2, lw=0.8)
    ax.set(title="Para que lado cada atributo empurra o score (média no teste)", xlabel="contribuição média (log-odds)")
    ax.legend(loc="lower right")
    ax.grid(axis="y", visible=False)
    g.salvar(fig, "risco_direcao_fatores.png"); plt.close(fig)


def fig_equidade(eq: dict[str, Any], nome: str) -> None:
    attrs = list(eq)
    fig, axes = plt.subplots(len(attrs), 1, figsize=(8, 2.1 * len(attrs)))
    for ax, a in zip(axes, attrs):
        vals = {k: v for k, v in eq[a].items() if isinstance(v.get("n"), int) and v.get("recall") is not None}
        nomes = list(vals)
        y = np.arange(len(nomes))
        ax.barh(y + 0.2, [vals[k]["recall"] * 100 for k in nomes], 0.38, color=g.SERIE[0], label="Recall")
        ax.barh(y - 0.2, [vals[k]["taxa_falsos_positivos"] * 100 for k in nomes], 0.38, color=g.SERIE[1], label="Falsos positivos")
        ax.set_yticks(y, [f"{k} (n={vals[k]['n']})" for k in nomes], fontsize=8)
        ax.set_xlim(0, 100)
        ax.set_title(a, fontsize=10)
        ax.grid(axis="y", visible=False)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper right", ncol=2, bbox_to_anchor=(1.0, 0.985))
    axes[-1].set_xlabel("%")
    fig.suptitle("Recall e taxa de falsos positivos por subgrupo (modelo final, teste)", x=0.01, ha="left",
                 fontsize=12, weight="bold")
    g.salvar(fig, nome); plt.close(fig)


def fig_variantes(var: dict[str, Any]) -> None:
    nomes = list(var)
    fig, ax = plt.subplots(figsize=(7, 3.6))
    x = np.arange(len(nomes))
    for i, (k, rot) in enumerate((("auc", "AUC"), ("recall", "Recall"), ("precisao", "Precisão"))):
        vals = [var[n]["geral"][k] for n in nomes]
        ax.bar(x + (i - 1) * 0.26, vals, 0.24, color=g.SERIE[i], label=rot)
        for xi, v in zip(x, vals):
            ax.text(xi + (i - 1) * 0.26, v + 0.01, f"{v:.3f}", ha="center", fontsize=8, color=g.TEXTO_2)
    ax.set_xticks(x, [n.replace("_", " ") for n in nomes], fontsize=9)
    ax.set(ylim=(0, 1.08), title="Variantes de atributos (mesma carga de contatos)")
    ax.legend(loc="lower right", ncol=3)
    ax.grid(axis="x", visible=False)
    g.salvar(fig, "risco_variantes_equidade.png"); plt.close(fig)


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def executar(verbose: bool = True) -> dict[str, Any]:
    log = print if verbose else (lambda *a, **k: None)
    caminho_art = ARTIFACTS / "risco_v2.joblib"
    art = joblib.load(caminho_art)
    modelo = RiskModel(art)
    cand = joblib.load(ARTIFACTS / "candidatos.joblib")
    df, _ = dados.carregar_limpo()
    _, teste = dados.dividir(df)
    y = teste[dados.ALVO].to_numpy()
    X = normalizar_entrada(teste, modelo.colunas)
    lim, lim_rec = art["limiares"], art["limiares_recomendados"]

    # Comparação dos três algoritmos calibrados (mesmo conjunto de atributos)
    probs = {a: m.predict_proba(normalizar_entrada(teste, cand["colunas"][a]))[:, 1] for a, m in cand["calibrados"].items()}
    fig_curvas(y, probs)
    comparacao = {a: {"limiar_contrato": metricas_limiar(y, p, lim["amarelo"]),
                      "limiar_recomendado": metricas_limiar(y, p, lim_rec["amarelo"])} for a, p in probs.items()}

    # Modelo final
    p = modelo.probabilidades(teste)
    p_sem = art["explicador"].predict_proba(X)[:, 1]
    final = {
        "limiar_contrato": metricas_limiar(y, p, lim["amarelo"]),
        "limiar_recomendado": metricas_limiar(y, p, lim_rec["amarelo"]),
        "limiar_vermelho": metricas_limiar(y, p, lim["vermelho"]),
        "sem_calibrar_limiar_0_5": metricas_limiar(y, p_sem, 0.5),
    }
    fig_matriz(final["limiar_contrato"]["matriz_confusao"], f"Matriz de confusão · corte {lim['amarelo']:.2f}",
               "risco_matriz_confusao.png")
    fig_matriz(final["limiar_recomendado"]["matriz_confusao"], f"Matriz de confusão · corte {lim_rec['amarelo']:.2f}",
               "risco_matriz_confusao_recomendado.png")
    log(f"Final ({art['algoritmo']}): {final['limiar_contrato']}")

    tab_cap, curva = capacidade(y, p)
    e1 = {"pct_sinalizados": 0.3609, "recall": 0.7707, "precisao": 0.4180, "auc": 0.8200}  # E1: (674+484)/3209 sinalizados
    fig_capacidade(curva, tab_cap, e1["pct_sinalizados"], e1["recall"])

    fx = {f"Contrato (≥{lim['amarelo']:.2f} / ≥{lim['vermelho']:.2f})": faixas(y, p, lim),
          f"Recomendado (≥{lim_rec['amarelo']:.2f} / ≥{lim_rec['vermelho']:.2f})": faixas(y, p, lim_rec)}
    fig_faixas(fx)
    calib = fig_calibracao(y, p_sem, p, art["calibracao"])

    # Explicabilidade global
    contrib = modelo.contribuicoes(teste)
    perm = permutation_importance(art["modelo"], X, y, scoring="roc_auc", n_repeats=5, random_state=dados.SEMENTE, n_jobs=-1)
    perm_s = pd.Series(perm.importances_mean, index=modelo.colunas)
    fig_importancia(contrib, perm_s)
    try:
        import shap
        plt.figure()
        shap.summary_plot(contrib.to_numpy(), normalizar_entrada(teste, modelo.colunas).apply(
            lambda c: c if pd.api.types.is_numeric_dtype(c) else pd.factorize(c)[0]).to_numpy(dtype=float),
            feature_names=[c.replace("_", " ") for c in modelo.colunas], show=False, max_display=14)
        plt.title("SHAP por aluno (teste) · cor = valor do atributo", loc="left", fontsize=11)
        g.salvar(plt.gcf(), "risco_shap_resumo.png"); plt.close("all")
    except ImportError:
        pass
    # Exemplo sintético (não é um aluno real): perfil típico de risco, só para mostrar o formato.
    exemplo_sintetico = {
        "tempo_de_curso": 1, "idade": 23, "mora_sp_capital": False, "total_parcelas": 12,
        "pct_parcelas_em_aberto": 0.42, "pct_parcelas_acordo": 0.1, "atraso_medio_dias": 21,
        "valor_total_periodo": 5200, "media_notas": 41, "media_assiduidade": 63, "pct_reprovacao": 0.4,
        "tendencia_notas": -12, "tendencia_assiduidade": -15, "total_semestres": 2,
        "forma_ingresso": "Vestibular", "grau_academico": "Bacharelado", "turno": "Noite", "tem_bolsa": False,
    }

    # Equidade: modelo final nos limiares ativos e recomendados
    grupos = dados.subgrupos(teste).reset_index(drop=True)
    eq_final = {"limiar_contrato": metricas_grupo(y, (p >= lim["amarelo"]).astype(int), grupos),
                "limiar_recomendado": metricas_grupo(y, (p >= lim_rec["amarelo"]).astype(int), grupos)}
    fig_equidade(eq_final["limiar_recomendado"], "risco_equidade_subgrupos.png")

    # Variantes de atributos com a mesma carga (mesma % de sinalizados do final no corte recomendado)
    carga = float((p >= lim_rec["amarelo"]).mean())
    alg = "xgboost" if art["algoritmo_codigo"].startswith("xgboost") else art["algoritmo_codigo"]
    variantes = {}
    for chave, m in cand["variantes"].items():
        nome, a = chave.split("|")
        if a != alg:
            continue
        cols = dados.CONJUNTOS[nome].todas
        pv = m.predict_proba(normalizar_entrada(teste, cols))[:, 1]
        corte = float(np.quantile(pv, 1 - carga))
        s = (pv >= corte).astype(int)
        pg = metricas_grupo(y, s, grupos)
        variantes[nome] = {"geral": {"auc": _r(roc_auc_score(y, pv)), "pr_auc": _r(average_precision_score(y, pv)),
                                     "recall": _r(recall_score(y, s)), "precisao": _r(precision_score(y, s)),
                                     "carga": _r(carga)},
                           "lacunas_entre_grupos": lacunas(pg), "por_grupo": pg}
    fig_variantes(variantes)

    # Erros (no corte recomendado, que é o de maior recall)
    sinal = (p >= lim_rec["amarelo"]).astype(int)
    pe = perfil_erros(teste.reset_index(drop=True), y, sinal, contrib.reset_index(drop=True))
    obs = observacoes_erros(pe, eq_final["limiar_recomendado"])

    avaliacao = {
        "gerado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        "modelo": {"versao": art["versao"], "algoritmo": art["algoritmo"], "conjunto": art["conjunto_features"],
                   "calibracao": art["calibracao"], "limiares_ativos": lim, "limiares_recomendados": lim_rec},
        "baseline_e1_teste": e1,
        "comparacao_teste_calibrados": comparacao,
        "final_teste": final,
        "capacidade": tab_cap,
        "faixas": fx,
        "calibracao": calib,
        "explicabilidade": {
            "media_abs_contribuicao": {k: _r(v) for k, v in contrib.abs().mean().sort_values(ascending=False).items()},
            "importancia_permutacao_auc": {k: _r(v) for k, v in perm_s.sort_values(ascending=False).items()},
            "exemplo_sintetico": {"entrada": exemplo_sintetico, "saida": modelo.predict(exemplo_sintetico)},
        },
        "equidade": {"final": eq_final, "variantes_mesma_carga": variantes,
                     "lacunas_final_recomendado": lacunas(eq_final["limiar_recomendado"])},
        "erros": {"corte": lim_rec["amarelo"], "perfil": pe, "observacoes": obs},
    }
    caminho = ARTIFACTS / "metrics.json"
    tudo = json.loads(caminho.read_text()) if caminho.exists() else {}
    tudo["avaliacao"] = avaliacao
    caminho.write_text(json.dumps(tudo, ensure_ascii=False, indent=2, default=str))

    # métricas servidas em /risco/modelo (no corte ativo)
    fc = final["limiar_contrato"]
    art["metricas"] = {"auc": fc["auc"], "recall": fc["recall"], "precisao": fc["precisao"], "f1": fc["f1"],
                       "pr_auc": fc["pr_auc"], "brier": fc["brier"], "conjunto": "teste (25%, semente 42)"}
    joblib.dump(art, caminho_art, compress=3)
    sha = hashlib.sha256(caminho_art.read_bytes()).hexdigest()
    escrever_model_version(art, tudo, sha)
    log(f"Avaliação salva. sha256 do artefato: {sha[:12]}…")
    return tudo


def justificativa(art: dict[str, Any], tr: dict[str, Any], fc: dict[str, Any]) -> list[str]:
    cv, esc = tr["comparacao_cv"], tr["escolha"]
    j = [
        f"Na validação cruzada do treino (5 folds), as árvores superam a logística por ~0,10 de AUC "
        f"(RL {cv['logistica']['cv']['auc']['media']:.3f}, RF {cv['random_forest']['cv']['auc']['media']:.3f}, "
        f"XGBoost {cv['xgboost']['cv']['auc']['media']:.3f}). RF e XGBoost empatam (diferença < 0,005); fica o XGBoost, "
        "que explica cada aluno de forma exata (TreeSHAP nativo) e gera um artefato muito menor. O teste não foi usado para escolher.",
    ]
    if "coerencia" in esc:
        c = esc["coerencia"]
        j.append(
            f"Restrições monotônicas (mais parcelas em aberto/atraso/reprovação → mais risco; mais nota/frequência → menos risco) "
            f"custam {c['custo_auc']:.3f} de AUC na CV ({c['auc_cv_livre']:.3f} → {c['auc_cv_monotonico']:.3f}). Sem elas, o modelo "
            "aprende artefatos do retrato pós-desfecho (ex.: 0% de parcelas em aberto associado a mais evasão) e mostraria ao "
            "atendente fatores contraditórios. Aceitas por custarem menos que o limite definido (0,03)."
        )
    if art["conjunto_features"].startswith("sem_sensiveis"):
        j.append("Sexo e Estado Civil retirados: perda de AUC < 0,01 na CV e as lacunas de recall/FPR entre grupos não pioram.")
    if "sem_contatos" in art["conjunto_features"]:
        j.append("total_contatos e dias_desde_ultimo_contato retirados (regra 5): a base não separa pedidos do estudante de "
                 "contatos ativos do ASA, então procurar o ASA poderia mudar o score.")
    j.append(f"Probabilidade calibrada ({art['calibracao']}, Brier {fc['brier']:.3f} no teste): o score se lê como chance de evasão.")
    return j


def escrever_model_version(art: dict[str, Any], tudo: dict[str, Any], sha: str) -> None:
    tr, av = tudo["treino"], tudo["avaliacao"]
    cv = tr["comparacao_cv"]
    fc, fr = av["final_teste"]["limiar_contrato"], av["final_teste"]["limiar_recomendado"]
    removidos = {
        "completo_e1": [],
        "sem_sensiveis": dados.SENSIVEIS,
        "sem_sensiveis_sem_contatos": [*dados.SENSIVEIS, *dados.CONTATOS],
    }[art["conjunto_features"].split("+")[0]]
    mv = {
        "versao": art["versao"],
        "artefato": "ml/artifacts/risco_v2.joblib",
        "sha256": sha,
        "treinado_em": art["treinado_em"],
        "algoritmo": art["algoritmo"],
        "hiperparametros": art["hiperparametros"],
        "calibracao": art["calibracao"],
        "conjunto_features": art["conjunto_features"],
        "features": art["colunas"],
        "features_removidas": removidos,
        "nunca_exibidos_como_fator": sorted(NUNCA_COMO_FATOR),
        "limiares_ativos": art["limiares"],
        "limiares_recomendados": art["limiares_recomendados"],
        "metricas_teste_limiar_ativo": {k: fc[k] for k in ("auc", "pr_auc", "brier", "recall", "precisao", "f1", "pct_sinalizados")},
        "metricas_teste_limiar_recomendado": {k: fr[k] for k in ("auc", "pr_auc", "brier", "recall", "precisao", "f1", "pct_sinalizados")},
        "cv_auc": {a: cv[a]["cv"]["auc"] for a in cv},
        "baseline_e1": av["baseline_e1_teste"],
        "justificativa": justificativa(art, tr, fc),
        "uso": "from risco.modelo import RiskModel; RiskModel.carregar(caminho).predict(features)",
        "aviso": "Apoio à decisão. Nenhuma ação deve ser tomada sem avaliação humana.",
    }
    (ARTIFACTS / "MODEL_VERSION.json").write_text(json.dumps(mv, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    executar()
