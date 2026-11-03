"""Inferência e explicação do modelo de risco (interface usada pelo backend).

Uso::

    from risco.modelo import RiskModel
    m = RiskModel.carregar("ml/artifacts/risco_v2.joblib")
    m.predict({"media_notas": 48, "pct_parcelas_em_aberto": 0.4, ...})
    # -> dict no formato InferenciaResultado do contrato (sem os campos de persistência)

Dependências: numpy, pandas, scikit-learn, joblib e (se o modelo final for de
árvore) xgboost. Nenhuma linha de treino é guardada no artefato: só objetos
ajustados do scikit-learn/xgboost e estatísticas agregadas (medianas, modas,
médias das colunas transformadas).

Regras do projeto aplicadas aqui:
- Atributos sensíveis (sexo, estado civil, idade) nunca aparecem como fator.
- Regra 5: contatos com o ASA nunca aparecem como fator que *aumenta* o risco.
- A recomendação é sempre de apoio, nunca punitiva.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

# Nomes do contrato (FeaturesRisco, snake_case) -> nomes da base de treino.
ALIASES_CONTRATO = {
    "idade": "Idade",
    "forma_ingresso": "Forma de Ingresso",
    "grau_academico": "Grau Acadêmico",
    "turno": "Turno",
    "estado_civil": "Estado Civil",
    "sexo": "Sexo",
}

NUNCA_COMO_FATOR = {"Sexo", "Estado Civil", "Idade"}
CONTATOS = {"total_contatos", "dias_desde_ultimo_contato"}

AVISO = "Apoio à decisão. Nenhuma ação deve ser tomada sem avaliação humana."


# ---------------------------------------------------------------------------
# Catálogo de fatores: código, dimensão e frase pronta para o atendente
# ---------------------------------------------------------------------------

def _pct(v: float) -> str:
    return f"{100 * v:.0f}%"


def _tendencia(nome: str, unidade: str) -> Callable[[Any, Mapping[str, Any]], str]:
    def f(v: Any, ref: Mapping[str, Any]) -> str:
        v = float(v)
        if v <= -1:
            return f"{nome} em queda ({v:+.0f} {unidade})"
        if v >= 1:
            return f"{nome} em alta ({v:+.0f} {unidade})"
        return f"{nome} estável"
    return f


def _atraso(v: Any, ref: Mapping[str, Any]) -> str:
    v = float(v)
    if v > 0.5:
        return f"Atraso médio de {v:.0f} dias nos pagamentos"
    if v < -0.5:
        return f"Pagamentos adiantados em média {abs(v):.0f} dias"
    return "Pagamentos em dia"


def _valor(v: Any, ref: Mapping[str, Any]) -> str:
    mediana = float(ref.get("valor_total_periodo", 0) or 0)
    if mediana and float(v) > 1.25 * mediana:
        return "Valor do período acima da mediana dos alunos"
    if mediana and float(v) < 0.75 * mediana:
        return "Valor do período abaixo da mediana dos alunos"
    return "Valor do período próximo da mediana dos alunos"


@dataclass(frozen=True)
class DefFator:
    codigo: str
    dimensao: str
    descrever: Callable[[Any, Mapping[str, Any]], str]


CATALOGO: dict[str, DefFator] = {
    # financeira
    "pct_parcelas_em_aberto": DefFator("parcelas_em_aberto", "financeira", lambda v, r: f"{_pct(float(v))} das parcelas em aberto"),
    "pct_parcelas_acordo": DefFator("parcelas_em_acordo", "financeira", lambda v, r: f"{_pct(float(v))} das parcelas em acordo"),
    "atraso_medio_dias": DefFator("atraso_pagamentos", "financeira", _atraso),
    "total_parcelas": DefFator("total_parcelas", "financeira", lambda v, r: f"{float(v):.0f} parcelas no contrato"),
    "valor_total_periodo": DefFator("valor_periodo", "financeira", _valor),
    "tem_bolsa": DefFator("bolsa_financiamento", "financeira",
                          lambda v, r: "Possui bolsa ou financiamento" if bool(v) else "Sem bolsa ou financiamento"),
    # acadêmica
    "media_notas": DefFator("media_notas", "academica", lambda v, r: f"Média de notas {float(v):.0f}/100"),
    "media_assiduidade": DefFator("frequencia", "academica", lambda v, r: f"Frequência média de {float(v):.0f}%"),
    "pct_reprovacao": DefFator("reprovacoes", "academica", lambda v, r: f"{_pct(float(v))} de reprovações nas disciplinas"),
    "tendencia_notas": DefFator("tendencia_notas", "academica", _tendencia("Notas", "pts")),
    "tendencia_assiduidade": DefFator("tendencia_frequencia", "academica", _tendencia("Frequência", "p.p.")),
    "sem_historico_academico": DefFator("sem_historico_academico", "academica",
                                        lambda v, r: "Sem notas e frequência lançadas" if float(v) >= 0.5
                                        else "Com notas e frequência lançadas"),
    "total_semestres": DefFator("semestres_cursados", "academica", lambda v, r: f"{float(v):.0f} semestres cursados"),
    "tempo_de_curso": DefFator("tempo_de_curso", "academica", lambda v, r: f"Tempo de curso: {float(v):.0f}"),
    "Forma de Ingresso": DefFator("forma_ingresso", "academica", lambda v, r: f"Ingresso por {v}"),
    "Grau Acadêmico": DefFator("grau_academico", "academica", lambda v, r: f"Curso de {v}"),
    "Turno": DefFator("turno", "academica", lambda v, r: f"Turno: {v}"),
    # relacionamento
    "mora_sp_capital": DefFator("regiao", "relacionamento",
                                lambda v, r: "Mora na capital" if float(v) >= 0.5 else "Mora fora da capital"),
    "total_contatos": DefFator("contatos_ativos_asa", "relacionamento", lambda v, r: f"{float(v):.0f} contatos ativos do ASA"),
    "dias_desde_ultimo_contato": DefFator("dias_sem_contato", "relacionamento",
                                          lambda v, r: f"{float(v):.0f} dias desde o último contato ativo do ASA"),
}

DIMENSOES = ("financeira", "academica", "relacionamento")

RECOMENDACOES = {
    "financeira": "Oferecer conversa sobre opções de apoio financeiro (bolsas, renegociação, auxílio emergencial).",
    "academica": "Oferecer apoio acadêmico (monitoria, coach acadêmico, plano de estudos) e verificar a frequência.",
    "relacionamento": "Fazer um contato de acolhimento para entender a situação e apresentar os serviços do ASA.",
}


def _sigmoide(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


# ---------------------------------------------------------------------------
# Preparação da entrada
# ---------------------------------------------------------------------------

def normalizar_entrada(features: Mapping[str, Any] | pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    """Aceita dict (nomes do contrato ou da base) ou DataFrame; devolve as colunas do modelo.

    Ausentes viram NaN (o pipeline imputa). ``media_notas`` é limitada a 100,
    como na limpeza da Entrega 1, e ``tem_bolsa`` vira 0/1.
    """
    if isinstance(features, pd.DataFrame):
        df = features.rename(columns=ALIASES_CONTRATO).copy()
    else:
        df = pd.DataFrame([{ALIASES_CONTRATO.get(k, k): v for k, v in features.items()}])
    for c in colunas:
        if c not in df.columns:
            df[c] = np.nan
    if "sem_historico_academico" in colunas:
        # Nota e frequência ambas 0 = nenhum lançamento acadêmico (ingresso recente, pós etc.), não "nota zero".
        notas = pd.to_numeric(df["media_notas"], errors="coerce")
        freq = pd.to_numeric(df["media_assiduidade"], errors="coerce")
        sem = (notas == 0) & (freq == 0)
        df["sem_historico_academico"] = sem.astype(float)
        df.loc[sem, ["media_notas", "media_assiduidade"]] = np.nan
    df = df[colunas].copy()
    if "media_notas" in df:
        df["media_notas"] = pd.to_numeric(df["media_notas"], errors="coerce").clip(upper=100)
    if "tem_bolsa" in df:
        df["tem_bolsa"] = df["tem_bolsa"].map(
            lambda v: np.nan if v is None or (isinstance(v, float) and math.isnan(v))
            else float(str(v).strip().lower() in {"1", "1.0", "true", "sim", "s"})
        )
    if "mora_sp_capital" in df:
        df["mora_sp_capital"] = df["mora_sp_capital"].map(
            lambda v: np.nan if v is None or (isinstance(v, float) and math.isnan(v))
            else float(str(v).strip().lower() in {"1", "1.0", "true", "sim", "s"})
        )
    return df


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------

class RiskModel:
    """Envelope do artefato ``risco_v2.joblib``.

    O artefato é um ``dict`` com:
      - ``modelo``: classificador calibrado (``predict_proba``) que recebe o DataFrame de features;
      - ``explicador``: pipeline não calibrado (mesmos hiperparâmetros) ajustado no treino inteiro;
      - ``tipo_explicacao``: ``linear`` | ``xgboost`` | ``ablacao``;
      - ``colunas``, ``origem_colunas_transformadas``, ``medias_transformadas``, ``referencia``;
      - ``limiares`` (``amarelo``, ``vermelho``), ``versao``, ``algoritmo``, ``treinado_em``, ``metricas``.
    """

    def __init__(self, artefato: dict[str, Any]):
        self.a = artefato
        self.colunas: list[str] = list(artefato["colunas"])
        self.limiares: dict[str, float] = dict(artefato["limiares"])
        self.versao: str = artefato["versao"]

    # ---- carga -----------------------------------------------------------
    @classmethod
    def carregar(cls, caminho: str | Path) -> RiskModel:
        return cls(joblib.load(caminho))

    # ---- metadados (schema ModeloInfo) ------------------------------------
    def info(self) -> dict[str, Any]:
        m = self.a.get("metricas", {})
        return {
            "versao": self.versao,
            "algoritmo": self.a["algoritmo"],
            "treinado_em": self.a["treinado_em"],
            "limiares": self.limiares,
            "metricas": {k: m[k] for k in ("auc", "recall", "precisao", "f1") if k in m},
            "features": self.colunas,
        }

    # ---- probabilidade -----------------------------------------------------
    def probabilidades(self, features: Mapping[str, Any] | pd.DataFrame) -> np.ndarray:
        X = normalizar_entrada(features, self.colunas)
        return self.a["modelo"].predict_proba(X)[:, 1]

    def categoria(self, p: float) -> str:
        if p >= self.limiares["vermelho"]:
            return "vermelho"
        if p >= self.limiares["amarelo"]:
            return "amarelo"
        return "verde"

    # ---- contribuições (log-odds, relativas ao aluno médio) ----------------
    def contribuicoes(self, features: Mapping[str, Any] | pd.DataFrame) -> pd.DataFrame:
        """Uma linha por aluno, uma coluna por atributo de origem (log-odds)."""
        X = normalizar_entrada(features, self.colunas)
        exp = self.a["explicador"]
        prep, clf = exp.named_steps["prep"], exp.named_steps["clf"]
        origem = self.a["origem_colunas_transformadas"]
        tipo = self.a["tipo_explicacao"]

        if tipo == "linear":
            Xt = np.asarray(prep.transform(X), dtype=float)
            contrib_t = (Xt - np.asarray(self.a["medias_transformadas"])) * clf.coef_[0]
        elif tipo == "xgboost":
            import xgboost as xgb

            Xt = prep.transform(X)
            if not isinstance(Xt, pd.DataFrame):
                Xt = pd.DataFrame(Xt, columns=prep.get_feature_names_out())
            contrib_t = clf.get_booster().predict(xgb.DMatrix(Xt.astype(float)), pred_contribs=True)[:, :-1]
        else:  # ablação: troca cada atributo pela referência (mediana/moda) e mede a variação do logit
            base = _logit_vec(exp.predict_proba(X)[:, 1])
            cols = {}
            for c in self.colunas:
                Xr = X.copy()
                Xr[c] = self.a["referencia"][c]
                cols[c] = base - _logit_vec(exp.predict_proba(Xr)[:, 1])
            return pd.DataFrame(cols, index=X.index)

        df = pd.DataFrame(contrib_t, columns=origem, index=X.index)
        return df.T.groupby(level=0, sort=False).sum().T.reindex(columns=self.colunas, fill_value=0.0)

    # ---- explicação no formato Fator do contrato ---------------------------
    def explicar(self, features: Mapping[str, Any], max_fatores: int = 6, minimo: float = 0.02) -> list[dict[str, Any]]:
        """Fatores (codigo, descricao, dimensao, direcao, peso) de um aluno.

        ``peso`` é a participação relativa |contribuição| entre os fatores listados (soma 1).
        Sensíveis nunca entram; contatos com o ASA nunca entram como "aumenta" (regra 5).
        """
        X = normalizar_entrada(features, self.colunas)
        c = self.contribuicoes(X).iloc[0]
        ref = self.a["referencia"]
        candidatos = []
        for col, v in c.items():
            if col in NUNCA_COMO_FATOR or col not in CATALOGO or abs(v) < minimo:
                continue
            if col in CONTATOS and v > 0:
                continue
            valor = X.iloc[0][col]
            if valor is None or (isinstance(valor, float) and math.isnan(valor)):
                continue
            candidatos.append((col, float(v), valor))
        candidatos.sort(key=lambda t: abs(t[1]), reverse=True)
        candidatos = candidatos[:max_fatores]
        total = sum(abs(v) for _, v, _ in candidatos) or 1.0
        fatores = []
        for col, v, valor in candidatos:
            d = CATALOGO[col]
            fatores.append({
                "codigo": d.codigo,
                "descricao": d.descrever(valor, ref),
                "dimensao": d.dimensao,
                "direcao": "aumenta" if v > 0 else "reduz",
                "peso": round(abs(v) / total, 3),
            })
        return fatores

    def scores_por_dimensao(self, features: Mapping[str, Any]) -> dict[str, float]:
        """Probabilidade considerando só os desvios de cada dimensão em relação ao aluno médio."""
        c = self.contribuicoes(features).iloc[0]
        base = _logit(self.a["taxa_base"])
        out = {}
        for dim in DIMENSOES:
            z = sum(float(v) for col, v in c.items() if col in CATALOGO and CATALOGO[col].dimensao == dim)
            out[dim] = round(_sigmoide(base + z), 4)
        return out

    def recomendacao(self, categoria: str, fatores: list[dict[str, Any]]) -> str:
        if categoria == "verde":
            return "Sem ação imediata. Manter o acompanhamento de rotina."
        aumentam = [f for f in fatores if f["direcao"] == "aumenta"]
        dim = aumentam[0]["dimensao"] if aumentam else "relacionamento"
        prefixo = "Contato prioritário. " if categoria == "vermelho" else ""
        return prefixo + RECOMENDACOES[dim]

    # ---- interface principal ----------------------------------------------
    def predict(self, features: Mapping[str, Any]) -> dict[str, Any]:
        """Formato ``InferenciaResultado`` do contrato (sem persistência)."""
        p = float(self.probabilidades(features)[0])
        cat = self.categoria(p)
        fatores = self.explicar(features)
        dims = self.scores_por_dimensao(features)
        return {
            "probabilidade": round(p, 4),
            "categoria": cat,
            "score": {
                "geral": round(p, 4),
                "financeiro": dims["financeira"],
                "academico": dims["academica"],
                "relacionamento": dims["relacionamento"],
            },
            "fatores": fatores,
            "recomendacao": self.recomendacao(cat, fatores),
            "versao_modelo": self.versao,
            "calculado_em": datetime.now(UTC).isoformat(timespec="seconds"),
            "aviso": AVISO,
        }


def _logit_vec(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


_MODELO_PADRAO: RiskModel | None = None


def explicar(features: Mapping[str, Any], caminho: str | Path | None = None) -> list[dict[str, Any]]:
    """Atalho: fatores de um aluno usando o artefato padrão (ml/artifacts/risco_v2.joblib)."""
    global _MODELO_PADRAO
    if caminho is not None:
        return RiskModel.carregar(caminho).explicar(features)
    if _MODELO_PADRAO is None:
        _MODELO_PADRAO = RiskModel.carregar(Path(__file__).resolve().parents[1] / "artifacts" / "risco_v2.joblib")
    return _MODELO_PADRAO.explicar(features)
