"""Recomendação de ação por regra (sempre SUGESTÃO de apoio, nunca punitiva) e prioridade."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

_FINANCEIROS = frozenset({"parcelas_em_aberto", "atraso_medio", "parcelas_em_acordo"})

_ACOES = {
    ("vermelho", "financeira"): "Contato do ASA nesta semana oferecendo orientação sobre acordo de parcelas "
    "e as bolsas e financiamentos disponíveis.",
    ("vermelho", "academica"): "Contato do ASA nesta semana para montar um plano de estudos com monitoria "
    "ou coach acadêmico.",
    ("vermelho", "relacionamento"): "Contato de acolhimento do ASA nesta semana para entender a situação "
    "do estudante e apresentar os serviços de apoio.",
    ("amarelo", "financeira"): "Enviar informações sobre negociação de parcelas e bolsas (Cesta de Serviços) "
    "e acompanhar no próximo mês.",
    ("amarelo", "academica"): "Convidar para plantão de monitoria e acompanhar a frequência nas próximas duas semanas.",
    ("amarelo", "relacionamento"): "Fazer contato de acolhimento apresentando os serviços do ASA para o semestre.",
}
_ROTINA = "Sem ação imediata. Manter acompanhamento de rotina."
_SUFIXO = " A decisão é do atendente."


def _dimensao_principal(fatores: Sequence[dict[str, Any]]) -> str | None:
    aumentam = [f for f in fatores if f.get("direcao") == "aumenta"]
    if not aumentam:
        return None
    # Pendência financeira tem precedência quando aparece entre os fatores que aumentam
    if any(f.get("codigo") in _FINANCEIROS for f in aumentam[:3]):
        return "financeira"
    return max(aumentam, key=lambda f: f.get("peso", 0)).get("dimensao")


def recomendar(categoria: str, fatores: Sequence[dict[str, Any]]) -> str:
    """Ex.: vermelho + parcelas em aberto -> contato do ASA oferecendo orientação sobre acordo."""
    if categoria == "verde":
        return _ROTINA
    dim = _dimensao_principal(fatores) or "relacionamento"
    texto = "Sugestão: " + _ACOES[(categoria, dim)]
    # Segunda frente quando o vermelho tem fatores fortes em outra dimensão
    if categoria == "vermelho":
        outras = {
            f.get("dimensao")
            for f in fatores
            if f.get("direcao") == "aumenta" and f.get("peso", 0) >= 0.2 and f.get("dimensao") != dim
        }
        outras.discard(None)
        if "academica" in outras:
            texto += " Avaliar também apoio acadêmico (monitoria)."
        elif "financeira" in outras:
            texto += " Avaliar também orientação financeira."
    return texto + _SUFIXO


def prioridade_sugerida(categoria: str, tendencia: str | None = None) -> str:
    if categoria == "vermelho":
        return "urgente" if tendencia == "subindo" else "alta"
    if categoria == "amarelo":
        return "media" if tendencia == "subindo" else "baixa"
    return "baixa"


def tendencia_de(atual: float | None, anterior: float | None, limite: float = 0.05) -> str:
    """Mesma regra da view vw_fila_risco (±0,05 em relação ao mês anterior)."""
    if atual is None or anterior is None:
        return "estavel"
    delta = atual - anterior
    if delta >= limite:
        return "subindo"
    if delta <= -limite:
        return "caindo"
    return "estavel"
