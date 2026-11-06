"""Metadados dos atributos do modelo de risco: dimensão, código e frase do fator.

Regras: atributos sensíveis (idade, sexo, estado civil) nunca viram fator
exibido; valores monetários exatos nunca aparecem na descrição (regra 2/LGPD);
`total_contatos` e `dias_desde_ultimo_contato` contam só contatos ATIVOS do
ASA (regra 5: procurar o ASA nunca aumenta o risco).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

NUMERICAS = [
    "tempo_de_curso",
    "total_parcelas",
    "pct_parcelas_em_aberto",
    "pct_parcelas_acordo",
    "atraso_medio_dias",
    "valor_total_periodo",
    "media_notas",
    "media_assiduidade",
    "pct_reprovacao",
    "tendencia_notas",
    "tendencia_assiduidade",
    "total_semestres",
    "total_contatos",
    "dias_desde_ultimo_contato",
    "idade",
]
BOOLEANAS = ["mora_sp_capital", "tem_bolsa"]
CATEGORICAS = ["forma_ingresso", "grau_academico", "turno", "estado_civil", "sexo"]
SENSIVEIS = frozenset({"idade", "sexo", "estado_civil"})
TODAS = NUMERICAS + BOOLEANAS + CATEGORICAS

# Colunas da base (base_unificada / estudantes_sinteticos.csv) -> nomes da API
COLUNAS_CSV = {
    "Forma de Ingresso": "forma_ingresso",
    "Grau Acadêmico": "grau_academico",
    "Turno": "turno",
    "Idade": "idade",
    "Estado Civil": "estado_civil",
    "Sexo": "sexo",
}


def _pct(v: float) -> str:
    return f"{v:.0%}"


@dataclass(frozen=True)
class Atributo:
    codigo: str
    dimensao: str  # financeira | academica | relacionamento
    descrever: Callable[[Any], str]


ATRIBUTOS: dict[str, Atributo] = {
    "pct_parcelas_em_aberto": Atributo(
        "parcelas_em_aberto", "financeira", lambda v: f"{_pct(v)} das parcelas em aberto"
    ),
    "pct_parcelas_acordo": Atributo("parcelas_em_acordo", "financeira", lambda v: f"{_pct(v)} das parcelas em acordo"),
    "atraso_medio_dias": Atributo(
        "atraso_medio",
        "financeira",
        lambda v: f"Atraso médio de {v:.0f} dias nos pagamentos" if v > 0 else "Pagamentos em dia ou antecipados",
    ),
    "tem_bolsa": Atributo(
        "bolsa", "financeira", lambda v: "Possui bolsa ou financiamento" if v else "Sem bolsa ou financiamento"
    ),
    "valor_total_periodo": Atributo(
        "valor_periodo", "financeira", lambda _: "Valor do período (faixa, sem valor exato)"
    ),
    "total_parcelas": Atributo("total_parcelas", "financeira", lambda v: f"{v:.0f} parcelas no histórico"),
    "media_notas": Atributo("media_notas", "academica", lambda v: f"Média de notas {v:.0f}/100"),
    "media_assiduidade": Atributo("assiduidade", "academica", lambda v: f"Assiduidade média de {v:.0f}%"),
    "pct_reprovacao": Atributo("reprovacoes", "academica", lambda v: f"{_pct(v)} das disciplinas com reprovação"),
    "tendencia_notas": Atributo(
        "tendencia_notas",
        "academica",
        lambda v: "Notas em queda no período" if v < 0 else "Notas estáveis ou em melhora",
    ),
    "tendencia_assiduidade": Atributo(
        "tendencia_assiduidade",
        "academica",
        lambda v: "Frequência em queda no período" if v < 0 else "Frequência estável ou em melhora",
    ),
    "total_semestres": Atributo("semestres_cursados", "academica", lambda v: f"{v:.0f} semestres cursados"),
    "tempo_de_curso": Atributo("tempo_de_curso", "academica", lambda v: f"Tempo de curso: {v:.0f}"),
    "forma_ingresso": Atributo("forma_ingresso", "academica", lambda v: f"Ingresso por {v}"),
    "grau_academico": Atributo("grau_academico", "academica", lambda v: f"Curso de {v}"),
    "turno": Atributo("turno", "academica", lambda v: f"Turno: {v}"),
    "total_contatos": Atributo("contatos_ativos", "relacionamento", lambda v: f"{v:.0f} contatos ativos do ASA"),
    "dias_desde_ultimo_contato": Atributo(
        "sem_contato_ativo", "relacionamento", lambda v: f"{v:.0f} dias sem contato ativo do ASA"
    ),
    "mora_sp_capital": Atributo(
        "regiao", "relacionamento", lambda v: "Mora na capital" if v else "Mora fora da capital"
    ),
}

CODIGOS_SENSIVEIS = frozenset({"idade", "sexo", "estado_civil"})
