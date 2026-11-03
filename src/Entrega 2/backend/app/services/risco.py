"""Inferência do risco (POST /risco/inferir) e metadados do modelo (GET /risco/modelo)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from app.core import metricas
from app.core.auth import Usuario
from app.core.erros import ErroAPI
from app.db.repositorio import ErroRepositorio, Repositorio
from app.risk.atributos import TODAS
from app.risk.modelo import RiskModel
from app.risk.recomendacao import prioridade_sugerida, recomendar, tendencia_de
from app.schemas import InferenciaEntrada
from app.services.auditoria import auditar


class ServicoRisco:
    def __init__(self, repo: Repositorio, modelo: RiskModel | None) -> None:
        self.repo = repo
        self.modelo = modelo

    def _modelo(self) -> RiskModel:
        if self.modelo is None:
            raise ErroAPI("indisponivel", "O modelo de risco não está disponível no momento.")
        return self.modelo

    def info(self) -> dict[str, Any]:
        return self._modelo().info()

    def inferir(self, usuario: Usuario, entrada: InferenciaEntrada) -> dict[str, Any]:
        modelo = self._modelo()
        estudante_id = str(entrada.estudante_id) if entrada.estudante_id else None
        try:
            if estudante_id:
                linha = self.repo.features_recentes(estudante_id)
                if not linha:
                    raise ErroAPI("nao_encontrado", "Estudante sem features registradas.")
                features = {k: linha.get(k) for k in TODAS}
                for k, v in features.items():  # numeric do Postgres chega como str/Decimal
                    if isinstance(v, str) and k not in (
                        "forma_ingresso",
                        "grau_academico",
                        "turno",
                        "estado_civil",
                        "sexo",
                    ):
                        features[k] = float(v)
            else:
                assert entrada.features is not None
                features = entrada.features.model_dump()
        except ErroRepositorio as e:
            raise ErroAPI("indisponivel") from e

        pred = modelo.predict(features)
        recomendacao = recomendar(pred.categoria, pred.fatores)
        agora = datetime.now(UTC)
        score_id = None
        if entrada.persistir and estudante_id:
            try:
                serie = self.repo.serie_scores(estudante_id, 1)
                anterior = float(serie[-1]["probabilidade"]) if serie else None
                score_id = self.repo.registrar_score(
                    {
                        "estudante_id": estudante_id,
                        "competencia": date(agora.year, agora.month, 1).isoformat(),
                        "probabilidade": pred.probabilidade,
                        "score_financeiro": pred.score["financeiro"],
                        "score_academico": pred.score["academico"],
                        "score_relacionamento": pred.score["relacionamento"],
                        "categoria": pred.categoria,
                        "fatores": pred.fatores,
                        "recomendacao": recomendacao,
                        "versao_modelo": pred.versao_modelo,
                        "prioridade_sugerida": prioridade_sugerida(
                            pred.categoria, tendencia_de(pred.probabilidade, anterior)
                        ),
                        "usuario_id": usuario.id,
                    }
                )
            except ErroRepositorio as e:
                raise ErroAPI("indisponivel") from e

        metricas.risco_inferencias_total.labels(pred.versao_modelo).inc()
        resultado = {
            "probabilidade": pred.probabilidade,
            "categoria": pred.categoria,
            "score": pred.score,
            "fatores": pred.fatores,
            "recomendacao": recomendacao,
            "versao_modelo": pred.versao_modelo,
            "calculado_em": agora,
            "persistido": score_id is not None,
            "score_id": score_id,
        }
        auditar(
            self.repo,
            usuario,
            "inferencia_risco",
            "scores_risco",
            score_id,
            entrada={
                "estudante_id": estudante_id,
                "simulacao": estudante_id is None,
                "persistir": entrada.persistir,
                "imputados": pred.imputados,
            },
            resultado={"probabilidade": pred.probabilidade, "categoria": pred.categoria, "score_id": score_id},
            versao=pred.versao_modelo,
        )
        return resultado
