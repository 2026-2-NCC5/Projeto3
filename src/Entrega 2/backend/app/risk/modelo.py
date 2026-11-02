"""Modelo de risco de evasão atrás de uma interface estável.

    RiskModel.predict(features) -> Predicao(probabilidade, categoria, score, fatores, versao_modelo)

Carregamento (`carregar_modelo`):
1. `RISK_MODEL_PATH` (artefato da sessão de ML, joblib) se existir;
2. senão, PLACEHOLDER: regressão logística treinada na hora com
   `seeds/estudantes_sinteticos.csv` (dados fictícios). Versão `rl-placeholder-seeds-*`.

Formato do artefato joblib esperado da sessão de ML (dict):
    {
      "modelo": <estimador sklearn com predict_proba(DataFrame)>,
      "features": [nomes da API, ver app/risk/atributos.py],
      "referencia": {feature: valor típico (mediana/moda)},
      "versao": "rl-baseline-1.0", "algoritmo": "Regressão Logística",
      "treinado_em": "2026-11-03T12:00:00-03:00",
      "metricas": {"auc": 0.82, "recall": 0.77, "precisao": ..., "f1": ...}
    }

Explicação (fatores) é agnóstica ao algoritmo: contribuição de cada atributo
= logit(p(x)) - logit(p(x com o atributo no valor de referência)). Para
regressão logística isso é exatamente coef * (x - ref). Direção = sinal,
peso = participação relativa entre os fatores exibidos. Score por dimensão =
sigmoide(logit(p_ref) + soma das contribuições daquela dimensão).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from app.risk.atributos import (
    ATRIBUTOS,
    BOOLEANAS,
    CATEGORICAS,
    COLUNAS_CSV,
    NUMERICAS,
    SENSIVEIS,
)

log = logging.getLogger("asa.risco")

MAX_FATORES = 6
CONTRIBUICAO_MINIMA = 0.02  # em logit; abaixo disso o fator é ruído


class ModeloIndisponivel(Exception):
    pass


def categoria_de(p: float, amarelo: float = 0.30, vermelho: float = 0.60) -> str:
    if p >= vermelho:
        return "vermelho"
    if p >= amarelo:
        return "amarelo"
    return "verde"


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sigmoide(z: float) -> float:
    return 1 / (1 + math.exp(-z))


@dataclass
class Predicao:
    probabilidade: float
    categoria: str
    score: dict[str, float]  # geral, financeiro, academico, relacionamento (0..1)
    fatores: list[dict[str, Any]]  # formato Fator do contrato
    versao_modelo: str
    imputados: list[str] = field(default_factory=list)


class RiskModel(Protocol):
    versao: str

    def predict(self, features: dict[str, Any]) -> Predicao: ...
    def info(self) -> dict[str, Any]: ...


class ModeloSklearn:
    """Envolve qualquer estimador com predict_proba sobre um DataFrame."""

    def __init__(
        self,
        estimador: Any,
        features: list[str],
        referencia: dict[str, Any],
        *,
        versao: str,
        algoritmo: str,
        treinado_em: str,
        metricas: dict[str, float],
        limiar_amarelo: float = 0.30,
        limiar_vermelho: float = 0.60,
    ) -> None:
        self._est = estimador
        self.features = list(features)
        self.referencia = dict(referencia)
        self.versao = versao
        self.algoritmo = algoritmo
        self.treinado_em = treinado_em
        self.metricas = metricas
        self.limiar_amarelo = limiar_amarelo
        self.limiar_vermelho = limiar_vermelho

    # ------------------------------------------------------------------ util
    def _linha(self, features: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        linha, imputados = {}, []
        for f in self.features:
            v = features.get(f)
            if v is None:
                v = self.referencia.get(f)
                imputados.append(f)
            if f in BOOLEANAS and v is not None:
                v = float(bool(v))
            linha[f] = v
        return linha, imputados

    def _proba(self, linhas: list[dict[str, Any]]) -> list[float]:
        import pandas as pd

        df = pd.DataFrame(linhas, columns=self.features)
        return [float(p) for p in self._est.predict_proba(df)[:, 1]]

    # ------------------------------------------------------------------ API
    def predict(self, features: dict[str, Any]) -> Predicao:
        x, imputados = self._linha(features)
        ref, _ = self._linha({})
        variacoes = []
        for f in self.features:
            alterada = dict(x)
            alterada[f] = ref[f]
            variacoes.append(alterada)
        probs = self._proba([x, ref, *variacoes])
        p, p_ref, p_sem = probs[0], probs[1], probs[2:]
        lx = _logit(p)
        contrib = {f: lx - _logit(ps) for f, ps in zip(self.features, p_sem, strict=True)}

        por_dim = {"financeira": 0.0, "academica": 0.0, "relacionamento": 0.0}
        for f, c in contrib.items():
            meta = ATRIBUTOS.get(f)
            if meta and f not in SENSIVEIS:
                por_dim[meta.dimensao] += c
        base = _logit(p_ref)
        score = {
            "geral": round(p, 4),
            "financeiro": round(_sigmoide(base + por_dim["financeira"]), 4),
            "academico": round(_sigmoide(base + por_dim["academica"]), 4),
            "relacionamento": round(_sigmoide(base + por_dim["relacionamento"]), 4),
        }
        return Predicao(
            probabilidade=round(p, 4),
            categoria=categoria_de(p, self.limiar_amarelo, self.limiar_vermelho),
            score=score,
            fatores=self._fatores(x, contrib, imputados),
            versao_modelo=self.versao,
            imputados=imputados,
        )

    def _fatores(self, x: dict[str, Any], contrib: dict[str, float], imputados: list[str]) -> list[dict[str, Any]]:
        candidatos = [
            (f, c)
            for f, c in contrib.items()
            if f not in SENSIVEIS and f in ATRIBUTOS and f not in imputados and abs(c) >= CONTRIBUICAO_MINIMA
        ]
        candidatos.sort(key=lambda fc: -abs(fc[1]))
        candidatos = candidatos[:MAX_FATORES]
        total = sum(abs(c) for _, c in candidatos) or 1.0
        fatores = []
        for f, c in candidatos:
            meta = ATRIBUTOS[f]
            fatores.append(
                {
                    "codigo": meta.codigo,
                    "descricao": meta.descrever(x[f]),
                    "dimensao": meta.dimensao,
                    "direcao": "aumenta" if c > 0 else "reduz",
                    "peso": round(abs(c) / total, 2),
                }
            )
        return fatores

    def info(self) -> dict[str, Any]:
        return {
            "versao": self.versao,
            "algoritmo": self.algoritmo,
            "treinado_em": self.treinado_em,
            "limiares": {"amarelo": self.limiar_amarelo, "vermelho": self.limiar_vermelho},
            "metricas": self.metricas,
            "features": [f for f in self.features if f not in SENSIVEIS],
        }


# ---------------------------------------------------------------------------
# Placeholder treinável com os seeds (dados fictícios)
# ---------------------------------------------------------------------------
FEATURES_PLACEHOLDER = [f for f in NUMERICAS + BOOLEANAS + CATEGORICAS if f not in SENSIVEIS]


def treinar_placeholder(
    caminho_csv: Path,
    *,
    versao: str = "rl-placeholder-seeds-0.1",
    limiar_amarelo: float = 0.30,
    limiar_vermelho: float = 0.60,
) -> ModeloSklearn:
    """RL com class_weight=balanced (mesma receita da baseline da Entrega 1),
    SEM atributos sensíveis. Métricas num holdout de 25% e depois refit no todo."""
    import pandas as pd
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    df = pd.read_csv(caminho_csv).rename(columns=COLUNAS_CSV)
    for b in BOOLEANAS:
        df[b] = df[b].map(lambda v: float(str(v).strip().lower() in ("1", "1.0", "true", "sim")))
    numericas = [f for f in FEATURES_PLACEHOLDER if f in NUMERICAS or f in BOOLEANAS]
    categoricas = [f for f in FEATURES_PLACEHOLDER if f in CATEGORICAS]
    X, y = df[FEATURES_PLACEHOLDER], df["evadiu"].astype(int)

    def pipeline() -> Pipeline:
        prep = ColumnTransformer(
            [
                ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("esc", StandardScaler())]), numericas),
                (
                    "cat",
                    Pipeline(
                        [
                            ("imp", SimpleImputer(strategy="most_frequent")),
                            ("oh", OneHotEncoder(handle_unknown="ignore")),
                        ]
                    ),
                    categoricas,
                ),
            ]
        )
        return Pipeline([("prep", prep), ("rl", LogisticRegression(class_weight="balanced", max_iter=2000))])

    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)
    m = pipeline().fit(Xtr, ytr)
    prob = m.predict_proba(Xte)[:, 1]
    pred = (prob >= 0.5).astype(int)
    metricas = {
        "auc": round(float(roc_auc_score(yte, prob)), 4),
        "recall": round(float(recall_score(yte, pred)), 4),
        "precisao": round(float(precision_score(yte, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(yte, pred)), 4),
    }
    final = pipeline().fit(X, y)
    referencia: dict[str, Any] = {f: float(X[f].median()) for f in numericas}
    referencia.update({f: X[f].mode().iloc[0] for f in categoricas})
    return ModeloSklearn(
        final,
        FEATURES_PLACEHOLDER,
        referencia,
        versao=versao,
        algoritmo="Regressão Logística (placeholder treinado com seeds fictícios)",
        treinado_em=datetime.now(UTC).isoformat(timespec="seconds"),
        metricas=metricas,
        limiar_amarelo=limiar_amarelo,
        limiar_vermelho=limiar_vermelho,
    )


def carregar_artefato(caminho: Path, limiar_amarelo: float = 0.30, limiar_vermelho: float = 0.60) -> ModeloSklearn:
    import joblib

    art = joblib.load(caminho)
    if not isinstance(art, dict) or "modelo" not in art or "features" not in art:
        raise ModeloIndisponivel(f"artefato {caminho.name} fora do formato esperado (ver app/risk/modelo.py)")
    return ModeloSklearn(
        art["modelo"],
        list(art["features"]),
        dict(art.get("referencia") or {}),
        versao=str(art.get("versao", "desconhecida")),
        algoritmo=str(art.get("algoritmo", "")),
        treinado_em=str(art.get("treinado_em", "")),
        metricas=dict(art.get("metricas") or {}),
        limiar_amarelo=limiar_amarelo,
        limiar_vermelho=limiar_vermelho,
    )


def carregar_modelo(
    caminho_artefato: Path, caminho_seeds: Path, limiar_amarelo: float = 0.30, limiar_vermelho: float = 0.60
) -> ModeloSklearn | None:
    if caminho_artefato.is_file():
        try:
            m = carregar_artefato(caminho_artefato, limiar_amarelo, limiar_vermelho)
            log.info("modelo de risco carregado", extra={"versao_modelo": m.versao, "origem": "artefato"})
            return m
        except Exception:
            log.exception("falha ao carregar o artefato; tentando o placeholder")
    if caminho_seeds.is_file():
        m = treinar_placeholder(caminho_seeds, limiar_amarelo=limiar_amarelo, limiar_vermelho=limiar_vermelho)
        log.warning(
            "usando modelo PLACEHOLDER treinado com seeds fictícios",
            extra={"versao_modelo": m.versao, "metricas": m.metricas},
        )
        return m
    log.error("nenhum modelo de risco disponível (sem artefato e sem seeds)")
    return None
