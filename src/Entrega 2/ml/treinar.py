"""Treino do modelo de risco v2: comparação, busca, calibração, variantes de equidade.

    ASA_DATA_DIR=/caminho/para/data python ml/treinar.py

Gera:
  - ml/artifacts/risco_v2.joblib       (modelo calibrado + explicador + metadados; sem linhas de treino)
  - ml/artifacts/metrics.json          (seção "treino"; o avaliar.py completa as demais)
  - ml/artifacts/MODEL_VERSION.json    (escolha final e justificativa)

Todas as métricas de comparação usam validação cruzada estratificada (5 folds)
**dentro do treino**. O conjunto de teste (mesmo split 75/25, semente 42, da
Entrega 1) só é usado para reportar o desempenho final, nunca para escolher.
"""

from __future__ import annotations

import json
import sys
import warnings
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV, StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

from risco import dados
from risco.modelo import normalizar_entrada

ARTIFACTS = AQUI / "artifacts"
VERSAO = "risco-2.0.0"
SEMENTE = dados.SEMENTE
CV = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEMENTE)
NOMES = {"logistica": "Regressão Logística", "random_forest": "Random Forest", "xgboost": "XGBoost"}

# Distribuição-alvo das faixas (capacidade do ASA): 15% vermelho, 25% amarelo.
ALVO_VERMELHO = 0.15
ALVO_AMARELO_OU_MAIS = 0.40

warnings.filterwarnings("ignore", category=UserWarning)


# ---------------------------------------------------------------------------
# Pipelines e espaços de busca
# ---------------------------------------------------------------------------

def preprocessador(conj: dados.ConjuntoFeatures) -> ColumnTransformer:
    num = Pipeline([("imp", SimpleImputer(strategy="median")), ("esc", StandardScaler())])
    cat = Pipeline([
        ("imp", SimpleImputer(strategy="constant", fill_value="Nao informado")),
        ("oh", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    ct = ColumnTransformer([("num", num, list(conj.numericas)), ("cat", cat, list(conj.categoricas))])
    return ct.set_output(transform="pandas")  # nomes de coluna chegam ao XGBoost (restrições por nome)


def classificador(algoritmo: str, peso_positivo: float) -> Any:
    if algoritmo == "logistica":
        return LogisticRegression(max_iter=2000, class_weight="balanced", random_state=SEMENTE)
    if algoritmo == "random_forest":
        return RandomForestClassifier(n_estimators=400, class_weight="balanced_subsample",
                                      random_state=SEMENTE, n_jobs=-1)
    if algoritmo == "xgboost":
        return XGBClassifier(n_estimators=300, tree_method="hist", eval_metric="logloss",
                             scale_pos_weight=peso_positivo, random_state=SEMENTE, n_jobs=-1)
    raise ValueError(algoritmo)


ESPACOS: dict[str, dict[str, list[Any]]] = {
    "logistica": {"clf__C": [0.01, 0.03, 0.1, 0.3, 1.0, 3.0]},
    "random_forest": {
        "clf__max_depth": [None, 8, 12, 16],
        "clf__min_samples_leaf": [1, 5, 10, 20],
        "clf__max_features": ["sqrt", 0.5],
    },
    "xgboost": {
        "clf__n_estimators": [200, 300, 500],
        "clf__max_depth": [3, 4, 5, 6],
        "clf__learning_rate": [0.03, 0.05, 0.1],
        "clf__subsample": [0.8, 1.0],
        "clf__colsample_bytree": [0.7, 1.0],
        "clf__min_child_weight": [1, 5],
        "clf__reg_lambda": [1.0, 5.0],
    },
}
N_ITER = {"random_forest": 10, "xgboost": 20}
METRICAS_CV = {"auc": "roc_auc", "pr_auc": "average_precision", "brier": "neg_brier_score",
               "recall": "recall", "precisao": "precision", "f1": "f1"}


def pipeline(algoritmo: str, conj: dados.ConjuntoFeatures, peso_positivo: float, params: dict | None = None,
             monotonica: bool = False) -> Pipeline:
    p = Pipeline([("prep", preprocessador(conj)), ("clf", classificador(algoritmo, peso_positivo))])
    if params:
        p.set_params(**params)
    if monotonica:
        if algoritmo != "xgboost":
            raise ValueError("restrição monotônica só implementada para o XGBoost")
        p.set_params(clf__monotone_constraints={f"num__{c}": d for c, d in dados.MONOTONICAS.items()
                                                if c in conj.numericas})
    return p


# Candidatos finais: (algoritmo, usa atributos derivados + restrição monotônica)
CANDIDATOS = {
    "logistica": ("logistica", False),
    "random_forest": ("random_forest", False),
    "xgboost": ("xgboost", False),
    "xgboost_monotonico": ("xgboost", True),
}
NOMES["xgboost_monotonico"] = "XGBoost monotônico"
CUSTO_MAX_COERENCIA = 0.03  # perda de AUC aceitável em troca de explicações com direção coerente


def buscar(algoritmo: str, conj: dados.ConjuntoFeatures, X: pd.DataFrame, y: np.ndarray, peso: float):
    base = pipeline(algoritmo, conj, peso)
    comum = dict(scoring=METRICAS_CV, refit="auc", cv=CV, n_jobs=-1 if algoritmo == "logistica" else 3)
    if algoritmo in N_ITER:
        busca = RandomizedSearchCV(base, ESPACOS[algoritmo], n_iter=N_ITER[algoritmo],
                                   random_state=SEMENTE, **comum)
    else:
        busca = GridSearchCV(base, ESPACOS[algoritmo], **comum)
    busca.fit(X, y)
    i = busca.best_index_
    r = busca.cv_results_
    cv = {}
    for k in METRICAS_CV:
        m, s = float(r[f"mean_test_{k}"][i]), float(r[f"std_test_{k}"][i])
        if k == "brier":
            m = -m
        cv[k] = {"media": round(m, 4), "dp": round(s, 4)}
    params = {k.replace("clf__", ""): (v if not isinstance(v, np.generic) else v.item())
              for k, v in busca.best_params_.items()}
    return busca.best_estimator_, busca.best_params_, params, cv


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------

def metricas(y: np.ndarray, p: np.ndarray, limiar: float) -> dict[str, float]:
    pred = (p >= limiar).astype(int)
    return {
        "auc": round(float(roc_auc_score(y, p)), 4),
        "pr_auc": round(float(average_precision_score(y, p)), 4),
        "brier": round(float(brier_score_loss(y, p)), 4),
        "recall": round(float(recall_score(y, pred)), 4),
        "precisao": round(float(precision_score(y, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y, pred)), 4),
        "pct_sinalizados": round(float(pred.mean()), 4),
        "limiar": round(float(limiar), 4),
    }


def limiares_por_capacidade(p_oof: np.ndarray) -> dict[str, float]:
    """Cortes que deixam ~15% em Vermelho e ~25% em Amarelo nas previsões fora-da-dobra do treino."""
    return {
        "amarelo": round(float(np.quantile(p_oof, 1 - ALVO_AMARELO_OU_MAIS)), 4),
        "vermelho": round(float(np.quantile(p_oof, 1 - ALVO_VERMELHO)), 4),
    }


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

@dataclass
class Resultado:
    limpeza: dict[str, int]
    split: dict[str, Any]
    cv: dict[str, Any] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    modelos: dict[str, Pipeline] = field(default_factory=dict)        # não calibrados (melhores da busca)
    teste_sem_calibrar: dict[str, Any] = field(default_factory=dict)
    calibracao: dict[str, Any] = field(default_factory=dict)
    calibrados: dict[str, Any] = field(default_factory=dict)
    teste_calibrado: dict[str, Any] = field(default_factory=dict)
    variantes: dict[str, Any] = field(default_factory=dict)
    modelos_variantes: dict[str, Any] = field(default_factory=dict)
    escolha: dict[str, Any] = field(default_factory=dict)
    limiares: dict[str, Any] = field(default_factory=dict)
    robustez: dict[str, float] = field(default_factory=dict)


def preparar(df: pd.DataFrame, conj: dados.ConjuntoFeatures) -> pd.DataFrame:
    return normalizar_entrada(df, conj.todas)


def calibrar(modelo: Pipeline, X: pd.DataFrame, y: np.ndarray) -> tuple[str, dict[str, float], np.ndarray]:
    """Escolhe isotônica ou Platt pelo Brier fora-da-dobra no treino."""
    oof = {}
    for metodo in ("isotonic", "sigmoid"):
        cal = CalibratedClassifierCV(modelo, method=metodo, cv=5)
        oof[metodo] = cross_val_predict(cal, X, y, cv=CV, method="predict_proba", n_jobs=5)[:, 1]
    briers = {m: round(float(brier_score_loss(y, p)), 4) for m, p in oof.items()}
    melhor = min(briers, key=briers.get)
    return melhor, briers, oof[melhor]


def escolher(cv: dict[str, Any], variantes: dict[str, Any]) -> dict[str, Any]:
    """Regra de escolha (definida antes de olhar o teste):

    1. Algoritmo: o de maior AUC média na CV; se a vantagem sobre a logística for
       menor que 0,01 (dentro do ruído entre folds), fica a logística, que é
       explicável de forma exata pelos coeficientes.
       Entre as árvores, se a Random Forest ganhar do XGBoost por menos de 0,005,
       fica o XGBoost: explicação exata (TreeSHAP nativo, sem dependência extra)
       e artefato muito menor.
    2. Conjunto de atributos: o mais restrito (sem sexo/estado civil e sem contatos,
       regra 5) desde que perca menos de 0,01 de AUC na CV em relação ao completo.
    """
    melhor = max(cv, key=lambda a: cv[a]["auc"]["media"])
    if melhor == "random_forest" and cv[melhor]["auc"]["media"] - cv["xgboost"]["auc"]["media"] < 0.005:
        melhor = "xgboost"
    ganho = cv[melhor]["auc"]["media"] - cv["logistica"]["auc"]["media"]
    algoritmo = melhor if ganho >= 0.01 else "logistica"
    ordem = ["sem_sensiveis_sem_contatos", "sem_sensiveis", "completo_e1"]
    auc = {n: variantes[n][algoritmo]["cv_auc"] for n in ordem}
    conj = next(n for n in ordem if auc["completo_e1"] - auc[n] < 0.01)
    return {
        "algoritmo": algoritmo,
        "conjunto": conj,
        "melhor_auc_cv": melhor,
        "ganho_auc_cv_sobre_logistica": round(ganho, 4),
        "perda_auc_cv_vs_completo": round(auc["completo_e1"] - auc[conj], 4),
    }


def robustez_valor(treino: pd.DataFrame, conj: dados.ConjuntoFeatures, params: dict[str, Any], peso: float) -> dict[str, float]:
    """Quanto o XGBoost depende do valor exato de `valor_total_periodo` (preço de curso/turma)?"""
    y = treino[dados.ALVO].to_numpy()
    X = preparar(treino, conj)
    bp = {f"clf__{k}": v for k, v in params.items()}
    rng = np.random.default_rng(SEMENTE)
    versoes = {
        "original": X,
        "valor_em_decis": X.assign(valor_total_periodo=pd.qcut(X["valor_total_periodo"].rank(method="first"), 10, labels=False).astype(float)),
        "valor_com_ruido_5pct_dp": X.assign(valor_total_periodo=X["valor_total_periodo"] + rng.normal(0, 0.05 * X["valor_total_periodo"].std(), len(X))),
        "sem_valor": X.assign(valor_total_periodo=np.nan),
    }
    out = {}
    for nome, Xv in versoes.items():
        oof = cross_val_predict(pipeline("xgboost", conj, peso, bp), Xv, y, cv=CV, method="predict_proba", n_jobs=5)[:, 1]
        out[nome] = round(float(roc_auc_score(y, oof)), 4)
    return out


def executar(verbose: bool = True) -> Resultado:
    log = print if verbose else (lambda *a, **k: None)
    df, rel = dados.carregar_limpo()
    treino, teste = dados.dividir(df)
    y_tr, y_te = treino[dados.ALVO].to_numpy(), teste[dados.ALVO].to_numpy()
    peso = float((y_tr == 0).sum() / (y_tr == 1).sum())
    R = Resultado(
        limpeza=rel.como_dict(),
        split={"n_treino": len(treino), "n_teste": len(teste),
               "taxa_evasao_treino": round(dados.taxa_base(y_tr), 4),
               "taxa_evasao_teste": round(dados.taxa_base(y_te), 4),
               "semente": SEMENTE, "tamanho_teste": dados.TAMANHO_TESTE},
    )
    log(f"Limpeza: {R.limpeza}\nSplit: {R.split}")

    # 1) Comparação de algoritmos no conjunto completo da E1 (comparação justa com a baseline)
    completo = dados.CONJUNTOS["completo_e1"]
    Xtr, Xte = preparar(treino, completo), preparar(teste, completo)
    for alg in ("logistica", "random_forest", "xgboost"):
        est, bp, params, cv = buscar(alg, completo, Xtr, y_tr, peso)
        R.modelos[alg], R.params[alg], R.cv[alg] = est, params, cv
        R.teste_sem_calibrar[alg] = metricas(y_te, est.predict_proba(Xte)[:, 1], 0.5)
        log(f"[{alg}] CV AUC {cv['auc']['media']:.4f}±{cv['auc']['dp']:.4f} | PR-AUC {cv['pr_auc']['media']:.4f} | params {params}")

    # 2) Variantes de atributos (equidade e regra 5) com o melhor de cada algoritmo
    for nome, conj in dados.CONJUNTOS.items():
        Xv_tr, Xv_te = preparar(treino, conj), preparar(teste, conj)
        R.variantes[nome] = {}
        for alg in ("logistica", "random_forest", "xgboost"):
            bp = {f"clf__{k}": v for k, v in R.params[alg].items()}
            mod = pipeline(alg, conj, peso, bp)
            oof = cross_val_predict(mod, Xv_tr, y_tr, cv=CV, method="predict_proba", n_jobs=5)[:, 1]
            mod.fit(Xv_tr, y_tr)
            R.modelos_variantes[(nome, alg)] = mod
            R.variantes[nome][alg] = {
                "cv_auc": round(float(roc_auc_score(y_tr, oof)), 4),
                "cv_pr_auc": round(float(average_precision_score(y_tr, oof)), 4),
                "teste": metricas(y_te, mod.predict_proba(Xv_te)[:, 1], 0.5),
            }
        log(f"[variante {nome}] " + " | ".join(f"{a} CV AUC {v['cv_auc']}" for a, v in R.variantes[nome].items()))

    # 3) Escolha (só com números de CV)
    escolha = escolher(R.cv, R.variantes)
    R.escolha = escolha
    log(f"Escolha: {escolha}")

    R.robustez = robustez_valor(treino, dados.CONJUNTOS[escolha["conjunto"]], R.params["xgboost"], peso)
    log(f"Robustez (XGBoost, AUC OOF): {R.robustez}")

    # 4) Calibração dos candidatos (no conjunto escolhido) e limiares por capacidade
    conj = dados.CONJUNTOS[escolha["conjunto"]]
    for nome, (alg, mono) in CANDIDATOS.items():
        c = dados.com_derivadas(conj) if mono else conj
        Xtr, Xte = preparar(treino, c), preparar(teste, c)
        bp = {f"clf__{k}": v for k, v in R.params[alg].items()}
        base = pipeline(alg, c, peso, bp, monotonica=mono)
        metodo, briers, oof = calibrar(base, Xtr, y_tr)
        cal = CalibratedClassifierCV(base, method=metodo, cv=5).fit(Xtr, y_tr)
        lim = limiares_por_capacidade(oof)
        R.calibrados[nome] = cal
        R.calibracao[nome] = {"metodo": metodo, "brier_oof_treino": briers, "limiares_capacidade_oof": lim,
                              "auc_oof_calibrado": round(float(roc_auc_score(y_tr, oof)), 4),
                              "colunas": c.todas, "monotonica": mono, "_oof": oof}
        p_te = cal.predict_proba(Xte)[:, 1]
        R.teste_calibrado[nome] = {
            "limiar_amarelo_contrato_0_30": metricas(y_te, p_te, 0.30),
            "limiar_amarelo_capacidade": metricas(y_te, p_te, lim["amarelo"]),
        }
        log(f"[calibração {nome}] {metodo} Brier OOF {briers} | AUC OOF {R.calibracao[nome]['auc_oof_calibrado']} | limiares {lim}")

    # 4b) Coerência: o XGBoost monotônico substitui o livre se custar menos que CUSTO_MAX_COERENCIA de AUC (CV)
    final = escolha["algoritmo"]
    if final == "xgboost":
        custo = R.calibracao["xgboost"]["auc_oof_calibrado"] - R.calibracao["xgboost_monotonico"]["auc_oof_calibrado"]
        escolha["coerencia"] = {"auc_cv_livre": R.calibracao["xgboost"]["auc_oof_calibrado"],
                                "auc_cv_monotonico": R.calibracao["xgboost_monotonico"]["auc_oof_calibrado"],
                                "custo_auc": round(custo, 4), "custo_maximo": CUSTO_MAX_COERENCIA}
        if custo < CUSTO_MAX_COERENCIA:
            final = "xgboost_monotonico"
    escolha["final"] = final
    log(f"Final: {final} {escolha.get('coerencia', '')}")

    # 5) Limiares do artefato final
    alg = final
    oof = R.calibracao[alg]["_oof"]
    contrato = {"amarelo": 0.30, "vermelho": 0.60}
    dist_contrato = {
        "verde": round(float((oof < 0.30).mean()), 4),
        "amarelo": round(float(((oof >= 0.30) & (oof < 0.60)).mean()), 4),
        "vermelho": round(float((oof >= 0.60).mean()), 4),
    }
    q40 = float(np.quantile(oof, 1 - ALVO_AMARELO_OU_MAIS))
    vermelho_rec = 0.60 if 0.10 <= dist_contrato["vermelho"] <= 0.20 else round(float(np.quantile(oof, 1 - ALVO_VERMELHO)) * 20) / 20
    recomendado = {"amarelo": max(0.05, round(q40 * 20) / 20), "vermelho": vermelho_rec}
    dist_rec = {
        "verde": round(float((oof < recomendado["amarelo"]).mean()), 4),
        "amarelo": round(float(((oof >= recomendado["amarelo"]) & (oof < recomendado["vermelho"])).mean()), 4),
        "vermelho": round(float((oof >= recomendado["vermelho"]).mean()), 4),
    }
    R.limiares = {
        "contrato": contrato,
        "recomendado": recomendado,
        "distribuicao_recomendado_oof": dist_rec,
        "distribuicao_contrato_oof": dist_contrato,
        "capacidade": R.calibracao[alg]["limiares_capacidade_oof"],
        "alvo_distribuicao": {"verde": 1 - ALVO_AMARELO_OU_MAIS, "amarelo": ALVO_AMARELO_OU_MAIS - ALVO_VERMELHO,
                              "vermelho": ALVO_VERMELHO},
    }
    return R


def construir_artefato(R: Resultado, treino_df: pd.DataFrame, limiares: dict[str, float]) -> dict[str, Any]:
    final = R.escolha["final"]
    alg, mono = CANDIDATOS[final]
    conj = dados.CONJUNTOS[R.escolha["conjunto"]]
    conj = dados.com_derivadas(conj) if mono else conj
    X = preparar(treino_df, conj)
    y = treino_df[dados.ALVO].to_numpy()
    peso = float((y == 0).sum() / (y == 1).sum())
    bp = {f"clf__{k}": v for k, v in R.params[alg].items()}
    explicador = pipeline(alg, conj, peso, bp, monotonica=mono).fit(X, y)
    prep = explicador.named_steps["prep"]
    nomes_t = list(prep.get_feature_names_out())
    origem = []
    for n in nomes_t:
        bloco, resto = n.split("__", 1)
        origem.append(resto if bloco == "num" else next(c for c in conj.categoricas if resto.startswith(c + "_")))
    medias_t = np.asarray(prep.transform(X), dtype=float).mean(axis=0)
    referencia: dict[str, Any] = {c: float(X[c].median()) for c in conj.numericas}
    referencia.update({c: str(X[c].mode().iloc[0]) for c in conj.categoricas})
    tipo = {"logistica": "linear", "xgboost": "xgboost"}.get(alg, "ablacao")
    return {
        "versao": VERSAO,
        "algoritmo": NOMES[final],
        "algoritmo_codigo": final,
        "restricoes_monotonicas": {c: d for c, d in dados.MONOTONICAS.items() if c in conj.numericas} if mono else {},
        "conjunto_features": conj.nome,
        "treinado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        "colunas": conj.todas,
        "numericas": list(conj.numericas),
        "categoricas": list(conj.categoricas),
        "modelo": R.calibrados[final],
        "calibracao": R.calibracao[final]["metodo"],
        "explicador": explicador,
        "tipo_explicacao": tipo,
        "origem_colunas_transformadas": origem,
        "medias_transformadas": medias_t.tolist(),
        "referencia": referencia,
        "taxa_base": float(y.mean()),
        "limiares": limiares,
        "hiperparametros": R.params[alg],
        "metricas": {},
        "fonte_treino": "base real ASA (anonimizada, fora do Git); nenhuma linha embutida no artefato",
    }


def auditar_artefato(art: dict[str, Any], n_treino: int) -> None:
    """Garante que o artefato não carrega matriz de dados com o tamanho do treino."""
    def varrer(o: Any, prof: int = 0) -> None:
        if prof > 6:
            return
        if isinstance(o, pd.DataFrame):
            raise AssertionError("DataFrame embutido no artefato")
        if isinstance(o, np.ndarray) and o.ndim == 2 and o.shape[0] >= 0.1 * n_treino:
            raise AssertionError(f"Matriz {o.shape} suspeita no artefato")
        if isinstance(o, dict):
            for v in o.values():
                varrer(v, prof + 1)
        elif isinstance(o, (list, tuple)):
            for v in o[:50]:
                varrer(v, prof + 1)
        elif hasattr(o, "__dict__") and not isinstance(o, type):
            for v in vars(o).values():
                varrer(v, prof + 1)
    varrer(art)


def salvar(R: Resultado, politica_limiares: str = "contrato") -> dict[str, Any]:
    ARTIFACTS.mkdir(exist_ok=True)
    df, _ = dados.carregar_limpo()
    treino, _ = dados.dividir(df)
    lim = R.limiares["contrato"] if politica_limiares == "contrato" else R.limiares["capacidade"]
    art = construir_artefato(R, treino, dict(lim))
    art["politica_limiares"] = politica_limiares
    art["limiares_recomendados"] = dict(R.limiares["recomendado"])
    auditar_artefato(art, len(treino))
    joblib.dump(art, ARTIFACTS / "risco_v2.joblib", compress=3)
    # Candidatos (todos os algoritmos e variantes) só para o avaliar.py. Fica fora do Git (*.joblib).
    joblib.dump({"calibrados": R.calibrados, "conjunto": R.escolha["conjunto"],
                 "colunas": {n: c["colunas"] for n, c in R.calibracao.items()},
                 "variantes": {f"{n}|{a}": m for (n, a), m in R.modelos_variantes.items()}},
                ARTIFACTS / "candidatos.joblib", compress=3)

    calib = {a: {k: v for k, v in c.items() if not k.startswith("_")} for a, c in R.calibracao.items()}
    treino_json = {
        "versao": VERSAO,
        "gerado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        "limpeza": R.limpeza,
        "split": R.split,
        "comparacao_cv": {a: {"cv": R.cv[a], "hiperparametros": R.params[a]} for a in R.cv},
        "comparacao_teste_sem_calibrar_limiar_0_5": R.teste_sem_calibrar,
        "calibracao": calib,
        "comparacao_teste_calibrado": R.teste_calibrado,
        "variantes_atributos": R.variantes,
        "escolha": R.escolha,
        "robustez_valor_total_periodo_auc_cv": R.robustez,
        "limiares": R.limiares,
        "politica_limiares": politica_limiares,
    }
    caminho = ARTIFACTS / "metrics.json"
    atual = json.loads(caminho.read_text()) if caminho.exists() else {}
    atual["treino"] = treino_json
    caminho.write_text(json.dumps(atual, ensure_ascii=False, indent=2))
    return art


if __name__ == "__main__":
    politica = sys.argv[1] if len(sys.argv) > 1 else "contrato"
    R = executar()
    art = salvar(R, politica)
    print(f"Artefato salvo: {art['versao']} · {art['algoritmo']} · {art['conjunto_features']} · limiares {art['limiares']}")
