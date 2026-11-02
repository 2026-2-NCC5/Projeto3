"""Carga, limpeza e split da base de risco (mesmo tratamento da Entrega 1).

Os dados reais ficam em ``data/`` (fora do Git). O caminho pode ser trocado
pela variável de ambiente ``ASA_DATA_DIR``. Nada aqui grava linhas da base em
disco: as funções só devolvem DataFrames em memória.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

RAIZ_PROJETO = Path(__file__).resolve().parents[2]  # src/Entrega 2
ARQUIVO_BASE = "base_unificada_asa-final.csv"
ALVO = "evadiu"

SEMENTE = 42          # mesma da Entrega 1
TAMANHO_TESTE = 0.25  # mesmo split 75/25 estratificado da Entrega 1
LIMITE_ATRASO_SINALIZADO = -100.0  # regra da E1: atraso < -100 dias é sinalizado

# Atributos da Entrega 1 (ordem preservada).
NUMERICAS_E1 = [
    "tempo_de_curso", "Idade", "mora_sp_capital", "total_parcelas",
    "pct_parcelas_em_aberto", "pct_parcelas_acordo", "atraso_medio_dias",
    "valor_total_periodo", "media_notas", "media_assiduidade", "pct_reprovacao",
    "tendencia_notas", "tendencia_assiduidade", "total_semestres",
    "total_contatos", "dias_desde_ultimo_contato", "tem_bolsa",
]
# Na E1 `tem_bolsa` era one-hot; aqui entra como binário 0/1 (mesma informação).
CATEGORICAS_E1 = ["Forma de Ingresso", "Grau Acadêmico", "Turno", "Estado Civil", "Sexo"]

SENSIVEIS = ["Sexo", "Estado Civil"]                         # retirados na variante "sem_sensiveis"
CONTATOS = ["total_contatos", "dias_desde_ultimo_contato"]   # regra 5 (ver docs/decisoes/0001-fase0.md)


@dataclass(frozen=True)
class ConjuntoFeatures:
    """Um conjunto nomeado de atributos de entrada."""

    nome: str
    numericas: tuple[str, ...]
    categoricas: tuple[str, ...]

    @property
    def todas(self) -> list[str]:
        return [*self.numericas, *self.categoricas]


def conjunto(nome: str, remover: list[str] | tuple[str, ...] = ()) -> ConjuntoFeatures:
    return ConjuntoFeatures(
        nome=nome,
        numericas=tuple(c for c in NUMERICAS_E1 if c not in remover),
        categoricas=tuple(c for c in CATEGORICAS_E1 if c not in remover),
    )


DERIVADAS = ["sem_historico_academico"]  # calculada em risco.modelo.normalizar_entrada

# Direção esperada pelo domínio (+1 = valor maior aumenta o risco). Usada como restrição
# monotônica no XGBoost final para que nenhuma explicação contradiga o bom senso.
MONOTONICAS = {
    "pct_parcelas_em_aberto": 1, "pct_parcelas_acordo": 1, "atraso_medio_dias": 1, "pct_reprovacao": 1,
    "media_notas": -1, "media_assiduidade": -1, "tendencia_notas": -1, "tendencia_assiduidade": -1,
}

CONJUNTOS = {
    "completo_e1": conjunto("completo_e1"),
    "sem_sensiveis": conjunto("sem_sensiveis", SENSIVEIS),
    "sem_sensiveis_sem_contatos": conjunto("sem_sensiveis_sem_contatos", [*SENSIVEIS, *CONTATOS]),
}


def com_derivadas(conj: ConjuntoFeatures) -> ConjuntoFeatures:
    return ConjuntoFeatures(nome=conj.nome + "+derivadas", numericas=(*conj.numericas, *DERIVADAS),
                            categoricas=conj.categoricas)


def caminho_base() -> Path:
    pasta = Path(os.environ.get("ASA_DATA_DIR", RAIZ_PROJETO / "data"))
    arq = pasta / ARQUIVO_BASE
    if not arq.exists():
        raise FileNotFoundError(
            f"Base real não encontrada em {arq}. Defina ASA_DATA_DIR apontando para a pasta data/ local."
        )
    return arq


@dataclass
class RelatorioLimpeza:
    linhas_brutas: int
    duplicados_removidos: int
    notas_acima_100: int
    atraso_sinalizado: int
    linhas_finais: int

    def como_dict(self) -> dict[str, int]:
        return self.__dict__.copy()


def carregar_limpo() -> tuple[pd.DataFrame, RelatorioLimpeza]:
    """Lê a base real e aplica a limpeza da Entrega 1.

    - 7 alunos duplicados: mantém a primeira ocorrência.
    - ``media_notas`` > 100: capping em 100.
    - ``atraso_medio_dias`` < -100: só sinaliza (coluna ``flag_atraso_atipico``), não remove.
    """
    bruto = pd.read_csv(caminho_base())
    df = bruto.drop_duplicates(subset="ID_ALUNO", keep="first").reset_index(drop=True)
    notas_acima = int((df["media_notas"] > 100).sum())
    df["media_notas"] = df["media_notas"].clip(upper=100)
    df["flag_atraso_atipico"] = df["atraso_medio_dias"] < LIMITE_ATRASO_SINALIZADO
    df[ALVO] = df[ALVO].astype(int)
    df["tem_bolsa"] = df["tem_bolsa"].astype(bool).astype(float)
    rel = RelatorioLimpeza(
        linhas_brutas=len(bruto),
        duplicados_removidos=len(bruto) - len(df),
        notas_acima_100=notas_acima,
        atraso_sinalizado=int(df["flag_atraso_atipico"].sum()),
        linhas_finais=len(df),
    )
    return df, rel


def dividir(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split 75/25 estratificado, semente 42 (idêntico ao da Entrega 1)."""
    treino, teste = train_test_split(df, test_size=TAMANHO_TESTE, random_state=SEMENTE, stratify=df[ALVO])
    return treino, teste


def faixa_etaria(idade: pd.Series) -> pd.Series:
    return pd.cut(idade, [0, 24, 29, 39, 200], labels=["até 24", "25–29", "30–39", "40+"]).astype(str)


def subgrupos(df: pd.DataFrame) -> pd.DataFrame:
    """Colunas usadas na análise de equidade (só para agregação, nunca exportadas por linha)."""
    return pd.DataFrame(
        {
            "Turno": df["Turno"].astype(str),
            "Forma de Ingresso": df["Forma de Ingresso"].astype(str),
            "Grau Acadêmico": df["Grau Acadêmico"].astype(str),
            "Faixa etária": faixa_etaria(df["Idade"]),
            "Sexo": df["Sexo"].astype(str),
        },
        index=df.index,
    )


def taxa_base(y: np.ndarray | pd.Series) -> float:
    return float(np.mean(y))
