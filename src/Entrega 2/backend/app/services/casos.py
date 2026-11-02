"""Fila de risco, detalhe do caso, validação humana e histórico."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core import metricas
from app.core.auth import Usuario
from app.core.erros import ErroAPI
from app.db.repositorio import (
    ConflitoVersao,
    ErroRepositorio,
    FiltrosFila,
    RegistroNaoEncontrado,
    Repositorio,
)
from app.rag.texto import normalizar
from app.risk.atributos import CODIGOS_SENSIVEIS
from app.risk.modelo import categoria_de
from app.risk.recomendacao import recomendar
from app.schemas import AVISO_APOIO, ValidacaoEntrada
from app.services.auditoria import auditar

MSG_CONFLITO_SCORE = "O score foi atualizado enquanto você analisava. Recarregue para ver a versão nova."
_ROTULO_STATUS = {
    "novo": "novo",
    "em_acompanhamento": "em acompanhamento",
    "contatado": "contatado",
    "resolvido": "resolvido",
    "arquivado": "arquivado",
}
_ROTULO_DECISAO = {"confirmado": "confirmou", "ajustado": "ajustou", "rejeitado": "rejeitou"}


def _estudante(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["estudante_id"],
        "ra": row["ra"],
        "nome": row.get("nome_exibicao") or "Estudante",
        "curso": row["curso"],
        "semestre": row["semestre_atual"],
        "faixa_distancia": row.get("faixa_distancia"),
        "regiao": row.get("regiao"),
    }


def _ref(uid: Any, nomes: dict[str, str]) -> dict[str, Any] | None:
    if not uid:
        return None
    return {"id": uid, "nome": nomes.get(str(uid), "Atendente")}


def filtrar_fatores(fatores: list[dict[str, Any]] | None, maximo: int = 8) -> list[dict[str, Any]]:
    """Remove atributos sensíveis (nunca exibidos) e renormaliza os pesos."""
    validos = [f for f in (fatores or []) if f.get("codigo") not in CODIGOS_SENSIVEIS][:maximo]
    total = sum(float(f.get("peso") or 0) for f in validos) or 1.0
    return [{**f, "peso": round(float(f.get("peso") or 0) / total, 2)} for f in validos]


class ServicoCasos:
    def __init__(self, repo: Repositorio) -> None:
        self.repo = repo

    def _db(self, fn: Any, *args: Any) -> Any:
        try:
            return fn(*args)
        except ErroRepositorio as e:
            raise ErroAPI("indisponivel") from e

    # ------------------------------------------------------------------ GET /casos
    def listar(self, usuario: Usuario, filtros: FiltrosFila) -> dict[str, Any]:
        if filtros.busca:
            filtros.busca = normalizar(filtros.busca)
        filtros.usuario_id = usuario.id
        pagina = self._db(self.repo.listar_fila, filtros)
        nomes = self._db(self.repo.nomes_perfis, [r.get("atendente_responsavel") for r in pagina.itens])
        itens = [
            {
                "estudante": _estudante(r),
                "caso_id": r.get("caso_id"),
                "score_geral": float(r["score_geral"]),
                "categoria": r["categoria"],
                "categoria_modelo": r["categoria_modelo"],
                "tendencia": r.get("tendencia") or "estavel",
                "variacao": float(r["variacao"]) if r.get("variacao") is not None else None,
                "status": r.get("status"),
                "prioridade": r.get("prioridade"),
                "prazo": r.get("prazo"),
                "responsavel": _ref(r.get("atendente_responsavel"), nomes),
                "ultima_decisao": r.get("ultima_decisao"),
                "versao_modelo": r["versao_modelo"],
                "atualizado_em": r["atualizado_em"],
            }
            for r in pagina.itens
        ]
        return {
            "total": pagina.total,
            "pagina": filtros.pagina,
            "por_pagina": filtros.por_pagina,
            "itens": itens,
            "contagem": pagina.contagem,
        }

    # ------------------------------------------------------------------ GET /casos/{id}
    def _validacao_saida(self, v: dict[str, Any], nomes: dict[str, str]) -> dict[str, Any]:
        return {
            "id": v["id"],
            "score_id": v.get("score_id"),
            "decisao": v["decisao"],
            "justificativa": v["justificativa"],
            "categoria_ajustada": v.get("categoria_ajustada"),
            "prioridade": v.get("prioridade_definida"),
            "prazo": v.get("prazo_definido"),
            "atendente": {
                "id": v["atendente_id"],
                "nome": v.get("atendente_nome") or nomes.get(str(v["atendente_id"]), "Atendente"),
            },
            "versao_modelo": v["versao_modelo"],
            "criado_em": v["criado_em"],
        }

    def detalhe(self, estudante_id: str) -> dict[str, Any]:
        row = self._db(self.repo.obter_item_fila, estudante_id)
        if not row:
            raise ErroAPI("nao_encontrado", "Estudante sem score de risco.")
        score = self._db(self.repo.obter_score, str(row["score_id"])) or {}
        serie = self._db(self.repo.serie_scores, estudante_id, 6)
        validacao = self._db(self.repo.ultima_validacao, str(row["caso_id"])) if row.get("caso_id") else None
        nomes = self._db(
            self.repo.nomes_perfis,
            [row.get("atendente_responsavel"), validacao.get("atendente_id") if validacao else None],
        )
        fatores = filtrar_fatores(score.get("fatores"))
        categoria = row["categoria"]
        return {
            "estudante": _estudante(row),
            "score_id": row["score_id"],
            "score": {
                "geral": float(row["score_geral"]),
                "financeiro": float(score.get("score_financeiro") or row.get("score_financeiro") or 0),
                "academico": float(score.get("score_academico") or row.get("score_academico") or 0),
                "relacionamento": float(score.get("score_relacionamento") or row.get("score_relacionamento") or 0),
            },
            "categoria": categoria,
            "categoria_modelo": row["categoria_modelo"],
            "fatores": fatores,
            "tendencia": [
                {"competencia": p["competencia"], "score_geral": float(p["probabilidade"]), "categoria": p["categoria"]}
                for p in serie
            ],
            # Regra do backend, aplicada à categoria VIGENTE (após validação humana)
            "recomendacao": recomendar(categoria, fatores),
            "caso": {
                "id": row.get("caso_id"),
                # Estudante sem caso aberto (em geral verde): caso "virtual", nada foi criado
                "status": row.get("status") or "novo",
                "prioridade": row.get("prioridade") or "baixa",
                "prazo": row.get("prazo"),
                "responsavel": _ref(row.get("atendente_responsavel"), nomes),
            },
            "ultima_validacao": self._validacao_saida(validacao, nomes) if validacao else None,
            "versao_modelo": row["versao_modelo"],
            "atualizado_em": row["atualizado_em"],
            "aviso": AVISO_APOIO,
        }

    # ------------------------------------------------------------------ POST /casos/{id}/validacao
    def validar(self, usuario: Usuario, estudante_id: str, entrada: ValidacaoEntrada) -> dict[str, Any]:
        dados = {
            "estudante_id": estudante_id,
            "score_id": str(entrada.score_id),
            "atendente_id": usuario.id,
            "decisao": entrada.decisao,
            "justificativa": entrada.justificativa.strip(),
            "categoria_ajustada": entrada.categoria_ajustada if entrada.decisao == "ajustado" else None,
            "prioridade": entrada.prioridade,
            "prazo": entrada.prazo.isoformat() if entrada.prazo else None,
            "status": entrada.status,
            "assumir_caso": entrada.assumir_caso,
        }
        try:
            v = self.repo.registrar_validacao(dados)
        except RegistroNaoEncontrado as e:
            raise ErroAPI("nao_encontrado", "Estudante sem score de risco.") from e
        except ConflitoVersao as e:
            raise ErroAPI("conflito", MSG_CONFLITO_SCORE) from e
        except ErroRepositorio as e:
            raise ErroAPI("indisponivel") from e
        metricas.validacoes_total.labels(entrada.decisao).inc()
        saida = self._validacao_saida(v, {usuario.id: usuario.nome})
        auditar(
            self.repo,
            usuario,
            "validacao_humana",
            "validacoes_caso",
            str(v["id"]),
            entrada={**dados, "justificativa": dados["justificativa"]},
            resultado={
                "validacao_id": str(v["id"]),
                "caso_id": str(v.get("caso_id")),
                "status_caso": v.get("caso_status"),
                "decisao": entrada.decisao,
            },
            versao=v.get("versao_modelo"),
        )
        return saida

    # ------------------------------------------------------------------ GET /casos/{id}/historico
    def historico(self, estudante_id: str, pagina: int, por_pagina: int) -> dict[str, Any]:
        if not self._db(self.repo.estudante_existe, estudante_id):
            raise ErroAPI("nao_encontrado", "Estudante não encontrado.")
        fontes = self._db(self.repo.eventos_historico, estudante_id)
        ids = [c.get("atendente_id") for c in fontes["contatos"]]
        ids += [v.get("atendente_id") for v in fontes["validacoes"]]
        ids += [e.get("usuario_id") for e in fontes["eventos"]]
        ids += [e.get("para") for e in fontes["eventos"] if e.get("tipo") == "responsavel"]
        ids += [e.get("de") for e in fontes["eventos"] if e.get("tipo") == "responsavel"]
        nomes = self._db(self.repo.nomes_perfis, [i for i in ids if i])

        eventos: list[dict[str, Any]] = []
        for s in fontes["scores"]:
            p = float(s["probabilidade"])
            eventos.append(
                {
                    "id": s["id"],
                    "tipo": "score",
                    "ocorrido_em": s["calculado_em"],
                    "usuario": None,
                    "descricao": f"Score calculado: {p:.0%} ({s['categoria']}) · "
                    f"competência {str(s['competencia'])[:7]}",
                    "dados": {"score_geral": p, "categoria": s["categoria"], "versao_modelo": s["versao_modelo"]},
                }
            )
        for v in fontes["validacoes"]:
            saida = self._validacao_saida(v, nomes)
            texto = f"{saida['atendente']['nome']} {_ROTULO_DECISAO[v['decisao']]} o alerta"
            if v.get("categoria_ajustada"):
                texto += f" (categoria ajustada para {v['categoria_ajustada']})"
            eventos.append(
                {
                    "id": v["id"],
                    "tipo": "validacao",
                    "ocorrido_em": v["criado_em"],
                    "usuario": saida["atendente"],
                    "descricao": texto,
                    "dados": saida,
                }
            )
        for c in fontes["contatos"]:
            quem = "Estudante procurou o ASA" if c["origem"] == "solicitacao_estudante" else "Contato ativo do ASA"
            eventos.append(
                {
                    "id": c["id"],
                    "tipo": "contato",
                    "ocorrido_em": c["ocorrido_em"],
                    "usuario": _ref(c.get("atendente_id"), nomes),
                    "descricao": f"{quem}: {c['motivo']} ({c['canal']})",
                    "dados": {
                        "origem": c["origem"],
                        "canal": c["canal"],
                        "motivo": c["motivo"],
                        "resultado": c.get("resultado"),
                    },
                }
            )
        for e in fontes["eventos"]:
            tipo = e["tipo"]
            if tipo not in ("status", "prioridade", "prazo", "responsavel", "criado"):
                continue
            de, para = e.get("de"), e.get("para")
            if tipo == "criado":
                texto = "Caso aberto para acompanhamento"
            elif tipo == "status":
                texto = f"Status: {_ROTULO_STATUS.get(de or '', de or '—')} → {_ROTULO_STATUS.get(para or '', para)}"
            elif tipo == "responsavel":
                texto = f"Responsável: {nomes.get(str(para), 'ninguém') if para else 'ninguém'}"
                de, para = (nomes.get(str(de), de) if de else None), (nomes.get(str(para), para) if para else None)
            else:
                texto = f"{tipo.capitalize()}: {de or '—'} → {para or '—'}"
            eventos.append(
                {
                    "id": e["id"],
                    "tipo": tipo,
                    "ocorrido_em": e["criado_em"],
                    "usuario": _ref(e.get("usuario_id"), nomes),
                    "descricao": texto,
                    "dados": {"de": de, "para": para, **(e.get("detalhes") or {})},
                }
            )

        def _quando(ev: dict[str, Any]) -> datetime:
            v = ev["ocorrido_em"]
            d = v if isinstance(v, datetime) else datetime.fromisoformat(str(v).replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=UTC)

        eventos.sort(key=_quando, reverse=True)
        ini = (pagina - 1) * por_pagina
        return {
            "total": len(eventos),
            "pagina": pagina,
            "por_pagina": por_pagina,
            "itens": eventos[ini : ini + por_pagina],
        }


__all__ = ["ServicoCasos", "categoria_de", "filtrar_fatores"]
