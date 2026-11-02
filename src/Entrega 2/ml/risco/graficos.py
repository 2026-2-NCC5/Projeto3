"""Estilo único das figuras PNG (docs/evidencias/)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

EVIDENCIAS = Path(__file__).resolve().parents[2] / "docs" / "evidencias"

SUPERFICIE = "#fcfcfb"
TEXTO = "#0b0b0b"
TEXTO_2 = "#52514e"
GRADE = "#e4e3df"

# Categóricas em ordem fixa (paleta validada, slots 1–3 passam em todos os pares).
SERIE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
COR_MODELO = {"logistica": SERIE[0], "random_forest": SERIE[1], "xgboost": SERIE[2], "xgboost_monotonico": SERIE[3]}
NOME_MODELO = {"logistica": "Regressão Logística", "random_forest": "Random Forest", "xgboost": "XGBoost",
               "xgboost_monotonico": "XGBoost monotônico"}

# Semáforo de risco: mesmos tons de web/src/styles/tokens.css (--risco-*-ponto). Uso exclusivo para faixas.
RISCO = {"verde": "#2f8a4f", "amarelo": "#c99200", "vermelho": "#c43a2b"}

# Polaridade dos fatores (aumenta/reduz): dois polos, nunca o semáforo.
AUMENTA, REDUZ = SERIE[1], SERIE[0]


def aplicar_estilo() -> None:
    plt.rcParams.update({
        "figure.facecolor": SUPERFICIE, "axes.facecolor": SUPERFICIE, "savefig.facecolor": SUPERFICIE,
        "axes.edgecolor": GRADE, "axes.labelcolor": TEXTO_2, "axes.titlecolor": TEXTO,
        "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.labelsize": 10, "xtick.color": TEXTO_2, "ytick.color": TEXTO_2,
        "xtick.labelsize": 9, "ytick.labelsize": 9,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRADE, "grid.linewidth": 0.6,
        "lines.linewidth": 2, "legend.frameon": False, "legend.fontsize": 9,
        "font.family": "DejaVu Sans", "figure.dpi": 110, "savefig.dpi": 150,
    })


def salvar(fig: plt.Figure, nome: str) -> Path:
    EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    caminho = EVIDENCIAS / nome
    fig.tight_layout()
    fig.savefig(caminho, bbox_inches="tight")
    return caminho


aplicar_estilo()
