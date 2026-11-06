"""Lê os JSONs de métricas e produz ml/artifacts/resultados_e2.json.

Uso:
    python ml/consolidar_resultados.py

Requer apenas stdlib (json, pathlib, hashlib, datetime).
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
ARTIFACTS = RAIZ / "artifacts"


def _hash_arquivo(caminho: Path) -> str:
    if not caminho.is_file():
        return ""
    h = hashlib.sha256()
    h.update(caminho.read_bytes())
    return h.hexdigest()


def _ler(caminho: Path) -> dict:
    if not caminho.is_file():
        print(f"[aviso] {caminho} não encontrado; seção omitida", file=sys.stderr)
        return {}
    return json.loads(caminho.read_text(encoding="utf-8"))


def consolidar() -> dict:
    metricas = _ler(ARTIFACTS / "metrics.json")
    rag = _ler(ARTIFACTS / "rag_metrics.json")
    model_ver = _ler(ARTIFACTS / "MODEL_VERSION.json")
    algebra = _ler(ARTIFACTS / "algebra_metrics.json")

    treino = metricas.get("treino", {})
    av = metricas.get("avaliacao", {})

    comparacao_cv = treino.get("comparacao_cv", {})
    final_teste = av.get("final_teste", {})
    capacidade = av.get("capacidade", [])
    faixas = av.get("faixas", {})
    calibracao = av.get("calibracao", [])
    explicabilidade = av.get("explicabilidade", {})
    equidade = av.get("equidade", {})
    erros = av.get("erros", {})
    limpeza = treino.get("limpeza", {})
    split = treino.get("split", {})
    variantes = treino.get("variantes_atributos", {})

    # --- RAG: extrair método escolhido e comparação
    rag_metodos = rag.get("metodos", {})
    rag_escolhido_key = rag.get("escolhido", {}).get("metodo", "")
    rag_escolhido = rag_metodos.get(rag_escolhido_key, {})
    groundedness = rag.get("groundedness", {})

    def _cv_resumo(modelo: str) -> dict:
        c = comparacao_cv.get(modelo, {}).get("cv", {})
        return {m: round(c.get(m, {}).get("media", 0), 4) for m in ("auc", "pr_auc", "recall", "precisao", "f1", "brier")}

    def _teste_resumo(modelo: str) -> dict:
        c = av.get("comparacao_teste_calibrados", {}).get(modelo, {})
        return {
            "auc": c.get("auc", 0),
            "pr_auc": c.get("pr_auc", 0),
            "recall": c.get("recall", 0),
            "precisao": c.get("precisao", 0),
            "f1": c.get("f1", 0),
            "brier": c.get("brier", 0),
        }

    resultado: dict = {
        "gerado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        "versao_relatorio": "2.0.0",
        "artefatos": {
            "modelo_joblib": str(ARTIFACTS / "risco_v2.joblib"),
            "sha256_modelo": _hash_arquivo(ARTIFACTS / "risco_v2.joblib"),
            "MODEL_VERSION_json": str(ARTIFACTS / "MODEL_VERSION.json"),
            "metrics_json": str(ARTIFACTS / "metrics.json"),
            "rag_metrics_json": str(ARTIFACTS / "rag_metrics.json"),
        },
        # ---- Dados ----
        "dados": {
            "linhas_brutas": limpeza.get("linhas_brutas", 0),
            "duplicados_removidos": limpeza.get("duplicados_removidos", 0),
            "outliers_atraso_sinalizado": limpeza.get("atraso_sinalizado", 0),
            "linhas_finais": limpeza.get("linhas_finais", 0),
            "n_treino": split.get("n_treino", 0),
            "n_teste": split.get("n_teste", 0),
            "taxa_evasao_treino": split.get("taxa_evasao_treino", 0),
            "taxa_evasao_teste": split.get("taxa_evasao_teste", 0),
            "semente": split.get("semente", 42),
        },
        # ---- Comparação CV ----
        "comparacao_cv": {
            "logistica": _cv_resumo("logistica"),
            "random_forest": _cv_resumo("random_forest"),
            "xgboost": _cv_resumo("xgboost"),
        },
        # ---- Comparação Teste (calibrado) ----
        "comparacao_teste_calibrado": {
            "logistica": _teste_resumo("logistica"),
            "random_forest": _teste_resumo("random_forest"),
            "xgboost": _teste_resumo("xgboost"),
            "xgboost_monotonico": _teste_resumo("xgboost_monotonico"),
        },
        # ---- Modelo escolhido ----
        "modelo_escolhido": {
            "algoritmo": model_ver.get("algoritmo", "XGBoost monotônico"),
            "versao": model_ver.get("versao", "risco-2.0.0"),
            "calibracao": model_ver.get("calibracao", "isotonic"),
            "conjunto_features": model_ver.get("conjunto_features", ""),
            "features": model_ver.get("features", []),
            "features_removidas": model_ver.get("features_removidas", []),
            "limiares_ativos": model_ver.get("limiares_ativos", {}),
            "limiares_recomendados": model_ver.get("limiares_recomendados", {}),
            "sha256": model_ver.get("sha256", ""),
            "treinado_em": model_ver.get("treinado_em", ""),
            "justificativa": model_ver.get("justificativa", []),
        },
        # ---- Métricas no teste ----
        "metricas_teste": {
            "limiar_contrato_0_30": final_teste.get("limiar_contrato", {}),
            "limiar_recomendado_0_10": final_teste.get("limiar_recomendado", {}),
            "limiar_vermelho_0_60": final_teste.get("limiar_vermelho", {}),
            "sem_calibrar": final_teste.get("sem_calibrar_limiar_0_5", {}),
        },
        # ---- Cobertura de atendimento ----
        "capacidade_cobertura": capacidade,
        # ---- Faixas de risco ----
        "faixas_risco": faixas,
        # ---- Calibração ----
        "calibracao": calibracao,
        # ---- Abstenção (outliers) ----
        "abstencao": {
            "regra": (
                "Registros com atraso_medio_dias > 365 ou NaN em todos os campos financeiros "
                "recebem categoria 'dados_insuficientes' e recomendação de revisão manual."
            ),
            "n_outliers_atraso_detectados_treino": limpeza.get("atraso_sinalizado", 0),
            "politica": treino.get("politica_limiares", {}),
        },
        # ---- Análise de erros ----
        "analise_erros": erros,
        # ---- Explicabilidade ----
        "explicabilidade": explicabilidade,
        # ---- Equidade ----
        "equidade": equidade,
        # ---- Variante sem sensíveis ----
        "variante_sem_sensiveis": variantes.get("sem_sensiveis", {}),
        # ---- RAG ----
        "rag": {
            "corpus": rag.get("corpus", {}),
            "perguntas": rag.get("perguntas", {}),
            "comparacao_metodos": {
                k: {
                    "nome": v.get("nome", k),
                    "recall_at_1": v.get("recuperacao", {}).get("dentro_do_escopo", {}).get("recall_at_1", 0),
                    "recall_at_3": v.get("recuperacao", {}).get("dentro_do_escopo", {}).get("recall_at_3", 0),
                    "mrr": v.get("recuperacao", {}).get("dentro_do_escopo", {}).get("mrr", 0),
                    "limiar_otimo": v.get("limiar_otimo", 0),
                    "acerto_do_agente": v.get("no_limiar_otimo", {}).get("acerto_do_agente", 0),
                    "abstencao_correta": v.get("no_limiar_otimo", {}).get("abstencao_correta", 0),
                    "abstencao_indevida": v.get("no_limiar_otimo", {}).get("abstencao_indevida", 0),
                    "acerto_cv": v.get("validacao_cruzada_limiar", {}).get("acerto_cv", 0),
                }
                for k, v in rag_metodos.items()
            },
            "escolhido": rag.get("escolhido", {}),
            "groundedness": groundedness,
            "revisao_amostra": rag.get("revisao_amostra", {}),
        },
        # ---- Baseline E1 ----
        "baseline_e1": model_ver.get("baseline_e1", av.get("baseline_e1_teste", {})),
        # ---- Álgebra linear ----
        "algebra_linear": algebra,
    }

    return resultado


def main() -> None:
    resultado = consolidar()
    saida = ARTIFACTS / "resultados_e2.json"
    saida.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[ok] {saida}")
    # Verificações básicas
    r = resultado
    auc_xgb = r["comparacao_cv"]["xgboost"]["auc"]
    auc_rl = r["comparacao_cv"]["logistica"]["auc"]
    recall_final = r["metricas_teste"]["limiar_recomendado_0_10"].get("recall", 0)
    print(f"     AUC-CV XGBoost: {auc_xgb:.4f}  |  RL: {auc_rl:.4f}")
    print(f"     Recall (limiar 0.10): {recall_final:.4f}")
    print(f"     RAG escolhido: {r['rag']['escolhido'].get('nome','?')}")
    print(f"     Recall@1 (bge-m3): {r['rag']['comparacao_metodos'].get('bge_m3',{}).get('recall_at_1',0):.4f}")


if __name__ == "__main__":
    main()
