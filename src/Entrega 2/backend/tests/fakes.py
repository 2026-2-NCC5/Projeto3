"""Dublês de teste: repositório em memória, provedores de embedding e emissor de JWT."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, date, datetime
from typing import Any

import jwt

from app.db.repositorio import ConflitoVersao, ErroRepositorio, FiltrosFila, PaginaFila, RegistroNaoEncontrado
from app.rag.embeddings import FalhaVetorizacao

SEGREDO_JWT = "segredo-de-teste-com-tamanho-suficiente-para-hs256"

ID_ESTUDANTE = "d0000000-0000-4000-8000-000000000001"  # perfil (login)
ID_ATENDENTE = "d0000000-0000-4000-8000-000000000002"
ID_ADMIN = "d0000000-0000-4000-8000-000000000003"
ID_TECNICO = "d0000000-0000-4000-8000-000000000004"
ID_OUTRO_ESTUDANTE = "d0000000-0000-4000-8000-000000000005"
EST_DEMO = "e0000000-0000-4000-8000-000000000001"  # estudantes.id do estudante demo
EST_OUTRO = "e0000000-0000-4000-8000-000000000005"
EST_RISCO = "e0000000-0000-4000-8000-0000000000aa"  # estudante na fila (vermelho)
EST_VERDE = "e0000000-0000-4000-8000-0000000000bb"
SCORE_RISCO = "50000000-0000-4000-8000-0000000000aa"
SCORE_VERDE = "50000000-0000-4000-8000-0000000000bb"
CASO_RISCO = "c0000000-0000-4000-8000-0000000000aa"
DOC_ATESTADO = "0c000000-0000-4000-8000-000000000001"
CHUNK_ATESTADO = "0c000000-0000-4000-8000-0000000000c1"
CHUNK_ATESTADO_LOCAL = "0c000000-0000-4000-8000-0000000000c2"
DOC_TRANCAMENTO = "0c000000-0000-4000-8000-000000000002"
CHUNK_TRANCAMENTO = "0c000000-0000-4000-8000-0000000000c3"
CHUNK_TRANCAMENTO_PRAZO = "0c000000-0000-4000-8000-0000000000c4"


def token(uid: str, *, exp_em: int = 3600, segredo: str = SEGREDO_JWT, aud: str = "authenticated") -> str:
    agora = int(time.time())
    return jwt.encode(
        {"sub": uid, "aud": aud, "exp": agora + exp_em, "iat": agora, "role": "authenticated"},
        segredo,
        algorithm="HS256",
    )


def auth(uid: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token(uid)}"}


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------
class ProvedorFalso:
    """Devolve um vetor fixo; ou falha (simula API fora / timeout)."""

    def __init__(self, nome: str = "falso", falhar: bool = False, dim: int = 4) -> None:
        self.nome = nome
        self.modelo = "@cf/baai/bge-m3" if nome != "huggingface" else "BAAI/bge-m3"
        self.falhar = falhar
        self.dim = dim
        self.chamadas: list[list[str]] = []

    def vetorizar(self, textos: Any) -> list[list[float]]:
        self.chamadas.append(list(textos))
        if self.falhar:
            raise FalhaVetorizacao("timeout simulado")
        return [[1.0] + [0.0] * (self.dim - 1) for _ in textos]


# ---------------------------------------------------------------------------
# Repositório em memória
# ---------------------------------------------------------------------------
def _agora() -> datetime:
    return datetime.now(UTC)


def _chunk(cid: str, did: str, titulo: str, conteudo: str) -> dict[str, Any]:
    return {
        "chunk_id": cid,
        "documento_id": did,
        "conteudo": conteudo,
        "titulo_documento": titulo,
        "fonte_documento": f"Cesta de Serviços ASA - {titulo}",
        "data_atualizacao": "2026-10-15T00:00:00+00:00",
    }


class RepoMemoria:
    def __init__(self) -> None:
        self.falhar: set[str] = set()  # nomes de métodos que levantam ErroRepositorio
        self.perfis = {
            ID_ESTUDANTE: {
                "id": ID_ESTUDANTE,
                "papel": "estudante",
                "nome_completo": "Júlia Prado (demo)",
                "email": "estudante.demo@example.com",
                "ativo": True,
            },
            ID_OUTRO_ESTUDANTE: {
                "id": ID_OUTRO_ESTUDANTE,
                "papel": "estudante",
                "nome_completo": "Outro Estudante",
                "email": "outro@example.com",
                "ativo": True,
            },
            ID_ATENDENTE: {
                "id": ID_ATENDENTE,
                "papel": "atendente",
                "nome_completo": "Atendente Demo",
                "email": "atendente.demo@example.com",
                "ativo": True,
            },
            ID_ADMIN: {
                "id": ID_ADMIN,
                "papel": "administrador",
                "nome_completo": "Admin Demo",
                "email": "admin.demo@example.com",
                "ativo": True,
            },
            ID_TECNICO: {
                "id": ID_TECNICO,
                "papel": "equipe_tecnica",
                "nome_completo": "Equipe Técnica",
                "email": "tec@example.com",
                "ativo": True,
            },
        }
        self.estudantes = {
            EST_DEMO: {
                "id": EST_DEMO,
                "perfil_id": ID_ESTUDANTE,
                "ra": "99999901",
                "curso": "Administração",
                "semestre_atual": 3,
                "nome_exibicao": "Júlia Prado (demo)",
            },
            EST_OUTRO: {
                "id": EST_OUTRO,
                "perfil_id": ID_OUTRO_ESTUDANTE,
                "ra": "99999905",
                "curso": "Marketing",
                "semestre_atual": 1,
                "nome_exibicao": "Outro Estudante",
            },
            EST_RISCO: {
                "id": EST_RISCO,
                "perfil_id": None,
                "ra": "99000111",
                "curso": "Ciências Contábeis",
                "semestre_atual": 2,
                "nome_exibicao": "Caio Antunes",
            },
            EST_VERDE: {
                "id": EST_VERDE,
                "perfil_id": None,
                "ra": "99000222",
                "curso": "Administração",
                "semestre_atual": 5,
                "nome_exibicao": "Lívia Araújo",
            },
        }
        # ---- RAG
        self.chunks = [
            _chunk(
                CHUNK_ATESTADO,
                DOC_ATESTADO,
                "Atestado de matrícula",
                "Atestado de matrícula: Precisa do atestado de matrícula? Basta acessar o Portal do Aluno, "
                "escolher a opção Relatórios e emitir o documento.",
            ),
            _chunk(
                CHUNK_ATESTADO_LOCAL,
                DOC_ATESTADO,
                "Atestado de matrícula",
                "Atestado de matrícula - Atendimento: Setor responsável: Secretaria Acadêmica.",
            ),
            _chunk(
                CHUNK_TRANCAMENTO,
                DOC_TRANCAMENTO,
                "Trancamento de matrícula",
                "Trancamento de matrícula: o trancamento é solicitado pelo Portal do Aluno em Requerimentos.",
            ),
            _chunk(
                CHUNK_TRANCAMENTO_PRAZO,
                DOC_TRANCAMENTO,
                "Trancamento de matrícula",
                "Trancamento de matrícula - Condições: 1) O prazo do trancamento segue o calendário "
                "acadêmico; 2) É preciso estar sem pendências na biblioteca",
            ),
        ]
        self.busca_resultado: list[dict[str, Any]] = []  # o que a "busca vetorial" devolve
        self.buscas: list[tuple[list[float], int]] = []
        # ---- chat
        self.conversas: dict[str, dict[str, Any]] = {}
        self.mensagens: list[dict[str, Any]] = []
        self.respostas: dict[str, dict[str, Any]] = {}
        self.feedbacks: list[dict[str, Any]] = []
        self.encaminhamentos: list[dict[str, Any]] = []
        # ---- risco
        self.scores: dict[str, dict[str, Any]] = {}
        self.casos: dict[str, dict[str, Any]] = {}
        self.validacoes: list[dict[str, Any]] = []
        self.eventos: list[dict[str, Any]] = []
        self.contatos: list[dict[str, Any]] = []
        self.features: dict[str, dict[str, Any]] = {}
        self._semear_risco()
        # ---- documentos
        self.documentos: dict[str, dict[str, Any]] = {}
        self.versoes: list[dict[str, Any]] = []
        self.chunks_docs: list[dict[str, Any]] = []
        # ---- auditoria
        self.auditoria: list[dict[str, Any]] = []

    # --------------------------------------------------------------- util
    def _check(self, nome: str) -> None:
        if nome in self.falhar or "*" in self.falhar:
            raise ErroRepositorio(f"falha simulada em {nome}")

    def _semear_risco(self) -> None:
        fatores = [
            {
                "codigo": "parcelas_em_aberto",
                "descricao": "40% das parcelas em aberto",
                "dimensao": "financeira",
                "direcao": "aumenta",
                "peso": 0.5,
            },
            {
                "codigo": "sexo",
                "descricao": "não deveria aparecer",
                "dimensao": "relacionamento",
                "direcao": "aumenta",
                "peso": 0.2,
            },
            {
                "codigo": "assiduidade",
                "descricao": "Assiduidade média de 70%",
                "dimensao": "academica",
                "direcao": "aumenta",
                "peso": 0.3,
            },
        ]
        for i, (mes, p, cat) in enumerate(
            [
                (5, 0.42, "amarelo"),
                (6, 0.48, "amarelo"),
                (7, 0.55, "amarelo"),
                (8, 0.58, "amarelo"),
                (9, 0.61, "vermelho"),
                (10, 0.72, "vermelho"),
            ]
        ):
            sid = SCORE_RISCO if mes == 10 else f"50000000-0000-4000-8000-00000000{i:04d}"
            self.scores[sid] = {
                "id": sid,
                "estudante_id": EST_RISCO,
                "competencia": date(2026, mes, 1),
                "probabilidade": p,
                "score_financeiro": 0.8,
                "score_academico": 0.6,
                "score_relacionamento": 0.3,
                "categoria": cat,
                "fatores": fatores,
                "recomendacao": None,
                "versao_modelo": "seed-sintetico-0",
                "calculado_em": datetime(2026, mes + 1, 1, 9, tzinfo=UTC),
            }
        self.scores[SCORE_VERDE] = {
            "id": SCORE_VERDE,
            "estudante_id": EST_VERDE,
            "competencia": date(2026, 10, 1),
            "probabilidade": 0.12,
            "score_financeiro": 0.1,
            "score_academico": 0.2,
            "score_relacionamento": 0.1,
            "categoria": "verde",
            "fatores": [],
            "recomendacao": None,
            "versao_modelo": "seed-sintetico-0",
            "calculado_em": datetime(2026, 11, 1, 9, tzinfo=UTC),
        }
        self.casos[CASO_RISCO] = {
            "id": CASO_RISCO,
            "estudante_id": EST_RISCO,
            "status": "novo",
            "prioridade": "alta",
            "prazo": date(2026, 11, 7),
            "atendente_responsavel": None,
            "score_atual_id": SCORE_RISCO,
            "categoria_vigente": None,
        }
        self.eventos.append(
            {
                "id": str(uuid.uuid4()),
                "caso_id": CASO_RISCO,
                "usuario_id": None,
                "tipo": "criado",
                "de": None,
                "para": "novo",
                "detalhes": {"origem": "seed"},
                "criado_em": datetime(2026, 11, 1, 9, tzinfo=UTC),
            }
        )
        self.contatos.append(
            {
                "id": str(uuid.uuid4()),
                "estudante_id": EST_RISCO,
                "atendente_id": None,
                "origem": "solicitacao_estudante",
                "canal": "presencial",
                "motivo": "Pedido de declaração",
                "resultado": None,
                "ocorrido_em": datetime(2026, 10, 20, 15, tzinfo=UTC),
            }
        )
        self.features[EST_RISCO] = {
            "estudante_id": EST_RISCO,
            "competencia": date(2026, 10, 1),
            "tempo_de_curso": 2,
            "total_parcelas": 20,
            "pct_parcelas_em_aberto": "0.40",
            "pct_parcelas_acordo": 0.1,
            "atraso_medio_dias": 25,
            "media_notas": 52,
            "media_assiduidade": 68,
            "pct_reprovacao": 0.3,
            "total_semestres": 2,
            "tendencia_notas": -5,
            "tem_bolsa": False,
            "turno": "Noite",
            "sexo": "Feminino",
            "idade": 22,
            "estado_civil": "Solteiro",
        }

    def _ultimo_score(self, estudante_id: str) -> dict[str, Any] | None:
        s = [x for x in self.scores.values() if x["estudante_id"] == estudante_id]
        return max(s, key=lambda x: (x["competencia"], x["calculado_em"])) if s else None

    def _linha_fila(self, estudante_id: str) -> dict[str, Any] | None:
        u = self._ultimo_score(estudante_id)
        if not u:
            return None
        e = self.estudantes[estudante_id]
        anteriores = [
            x
            for x in self.scores.values()
            if x["estudante_id"] == estudante_id
            and x["competencia"] < u["competencia"]
            and x["versao_modelo"] == u["versao_modelo"]
        ]
        ant = max(anteriores, key=lambda x: x["competencia"]) if anteriores else None
        caso = next((c for c in self.casos.values() if c["estudante_id"] == estudante_id), None)
        val = None
        if caso:
            vs = [v for v in self.validacoes if v["caso_id"] == caso["id"]]
            val = vs[-1] if vs else None
        var = round(u["probabilidade"] - ant["probabilidade"], 4) if ant else None
        tend = "estavel" if var is None else "subindo" if var >= 0.05 else "caindo" if var <= -0.05 else "estavel"
        return {
            "estudante_id": estudante_id,
            "ra": e["ra"],
            "nome_exibicao": e["nome_exibicao"],
            "curso": e["curso"],
            "semestre_atual": e["semestre_atual"],
            "faixa_distancia": "5_15km",
            "regiao": "Zona Oeste - SP",
            "score_id": u["id"],
            "score_geral": u["probabilidade"],
            "score_financeiro": u["score_financeiro"],
            "score_academico": u["score_academico"],
            "score_relacionamento": u["score_relacionamento"],
            "categoria_modelo": u["categoria"],
            "categoria": (caso or {}).get("categoria_vigente") or u["categoria"],
            "variacao": var,
            "tendencia": tend,
            "versao_modelo": u["versao_modelo"],
            "competencia": u["competencia"],
            "atualizado_em": u["calculado_em"],
            "caso_id": caso["id"] if caso else None,
            "status": caso["status"] if caso else None,
            "prioridade": caso["prioridade"] if caso else None,
            "prazo": caso["prazo"] if caso else None,
            "atendente_responsavel": caso["atendente_responsavel"] if caso else None,
            "ultima_decisao": val["decisao"] if val else None,
        }

    # --------------------------------------------------------------- operação / sessão
    def ping(self) -> None:
        self._check("ping")

    def obter_perfil(self, usuario_id: str) -> dict[str, Any] | None:
        self._check("obter_perfil")
        return self.perfis.get(usuario_id)

    def obter_estudante_por_perfil(self, perfil_id: str) -> dict[str, Any] | None:
        return next((e for e in self.estudantes.values() if e["perfil_id"] == perfil_id), None)

    def nomes_perfis(self, ids: list[str]) -> dict[str, str]:
        return {str(i): self.perfis[str(i)]["nome_completo"] for i in ids if i and str(i) in self.perfis}

    # --------------------------------------------------------------- RAG
    def buscar_chunks_similares(self, vetor: list[float], limite: int) -> list[dict[str, Any]]:
        self._check("buscar_chunks_similares")
        self.buscas.append((vetor, limite))
        return [dict(r) for r in self.busca_resultado[:limite]]

    def listar_chunks_ativos(self) -> list[dict[str, Any]]:
        self._check("listar_chunks_ativos")
        return [dict(c) for c in self.chunks]

    def resultado(self, chunk_id: str, similaridade: float) -> dict[str, Any]:
        c = next(c for c in self.chunks if c["chunk_id"] == chunk_id)
        return {**c, "similaridade": similaridade}

    # --------------------------------------------------------------- chat
    def obter_conversa(self, conversa_id: str) -> dict[str, Any] | None:
        self._check("obter_conversa")
        return self.conversas.get(conversa_id)

    def historico_conversa(self, conversa_id: str, limite: int) -> list[dict[str, Any]]:
        self._check("historico_conversa")
        msgs = [m for m in self.mensagens if m["conversa_id"] == conversa_id]
        return [{"remetente": m["remetente"], "conteudo": m["conteudo"]} for m in msgs][-limite:]

    def registrar_resposta_chat(self, d: dict[str, Any]) -> dict[str, Any]:
        self._check("registrar_resposta_chat")
        cid = d.get("conversa_id")
        agora = _agora()
        if not cid:
            cid = str(uuid.uuid4())
            self.conversas[cid] = {
                "id": cid,
                "estudante_id": d["estudante_id"],
                "status": "aberta",
                "titulo": d["titulo"],
                "iniciada_em": agora,
                "atualizado_em": agora,
            }
        elif self.conversas.get(cid, {}).get("estudante_id") != d["estudante_id"]:
            raise RegistroNaoEncontrado("conversa")
        self.mensagens.append(
            {
                "id": str(uuid.uuid4()),
                "conversa_id": cid,
                "remetente": "estudante",
                "conteudo": d["pergunta"],
                "criado_em": agora,
            }
        )
        mid = str(uuid.uuid4())
        self.mensagens.append(
            {"id": mid, "conversa_id": cid, "remetente": "agente", "conteudo": d["resposta"], "criado_em": agora}
        )
        self.respostas[d["resposta_id"]] = {**d, "id": d["resposta_id"], "mensagem_id": mid, "conversa_id": cid}
        enc = None
        if d["encaminhar"]:
            enc = next((e for e in self.encaminhamentos if e["conversa_id"] == cid and e["status"] == "aberto"), None)
            if not enc:
                enc = {
                    "id": str(uuid.uuid4()),
                    "conversa_id": cid,
                    "status": "aberto",
                    "setor_destino": "ASA",
                    "prazo": d["prazo_encaminhamento"],
                }
                self.encaminhamentos.append(enc)
            self.conversas[cid]["status"] = "encaminhada_humano"
        self.conversas[cid]["atualizado_em"] = agora
        return {
            "conversa_id": cid,
            "resposta_id": d["resposta_id"],
            "mensagem_id": mid,
            "encaminhamento": {k: enc[k] for k in ("id", "status", "setor_destino", "prazo")} if enc else None,
        }

    def listar_conversas(self, estudante_id: str, pagina: int, por_pagina: int) -> tuple[list[dict[str, Any]], int]:
        cs = sorted(
            (c for c in self.conversas.values() if c["estudante_id"] == estudante_id),
            key=lambda c: c["atualizado_em"],
            reverse=True,
        )
        ini = (pagina - 1) * por_pagina
        itens = []
        for c in cs[ini : ini + por_pagina]:
            msgs = [m for m in self.mensagens if m["conversa_id"] == c["id"]]
            itens.append({**c, "ultima_mensagem": msgs[-1]["conteudo"] if msgs else None})
        return itens, len(cs)

    def mensagens_conversa(self, conversa_id: str) -> list[dict[str, Any]]:
        saida = []
        for m in (m for m in self.mensagens if m["conversa_id"] == conversa_id):
            item = {k: m[k] for k in ("id", "remetente", "conteudo", "criado_em")}
            r = next((r for r in self.respostas.values() if r["mensagem_id"] == m["id"]), None)
            if r:
                fbs = [f for f in self.feedbacks if f["resposta_id"] == r["id"]]
                fontes = []
                for ev in r["evidencias"]:
                    c = next(c for c in self.chunks if c["chunk_id"] == ev["chunk_id"])
                    fontes.append(
                        {
                            "documento_id": c["documento_id"],
                            "titulo": c["titulo_documento"],
                            "fonte": c["fonte_documento"],
                            "data_atualizacao": c["data_atualizacao"],
                            "trecho": c["conteudo"],
                            "similaridade": ev["similaridade"],
                        }
                    )
                item["resposta"] = {
                    "resposta_id": r["id"],
                    "confianca": r["confianca"],
                    "abstencao": r["abstencao"],
                    "fontes": fontes,
                    "feedback": fbs[-1]["avaliacao"] if fbs else None,
                }
            saida.append(item)
        return saida

    def encaminhamento_da_conversa(self, conversa_id: str) -> dict[str, Any] | None:
        es = [e for e in self.encaminhamentos if e["conversa_id"] == conversa_id]
        return es[-1] if es else None

    def dono_da_resposta(self, resposta_id: str) -> str | None:
        r = self.respostas.get(resposta_id)
        return self.conversas[r["conversa_id"]]["estudante_id"] if r else None

    def salvar_feedback(
        self, resposta_id: str, estudante_id: str, avaliacao: str, comentario: str | None
    ) -> dict[str, Any]:
        self._check("salvar_feedback")
        self.feedbacks = [
            f for f in self.feedbacks if not (f["resposta_id"] == resposta_id and f["estudante_id"] == estudante_id)
        ]
        fb = {
            "id": str(uuid.uuid4()),
            "resposta_id": resposta_id,
            "estudante_id": estudante_id,
            "avaliacao": avaliacao,
            "comentario": comentario,
            "criado_em": _agora(),
        }
        self.feedbacks.append(fb)
        return fb

    # --------------------------------------------------------------- casos
    def listar_fila(self, f: FiltrosFila) -> PaginaFila:
        self._check("listar_fila")
        linhas = [r for e in self.estudantes if (r := self._linha_fila(e))]

        def passa(r: dict[str, Any], com_cat: bool) -> bool:
            if com_cat and f.categorias and r["categoria"] not in f.categorias:
                return False
            if f.prioridades and r["prioridade"] not in f.prioridades:
                return False
            if f.status and r["status"] not in f.status:
                return False
            if f.responsavel == "eu" and r["atendente_responsavel"] != f.usuario_id:
                return False
            if f.responsavel == "nenhum" and r["atendente_responsavel"] is not None:
                return False
            from app.rag.texto import normalizar

            return not (f.busca and f.busca not in normalizar(f"{r['nome_exibicao']} {r['ra']}"))

        filtradas = [r for r in linhas if passa(r, True)]
        ordem = {"urgente": 3, "alta": 2, "media": 1, "baixa": 0, None: -1}
        if f.ordenar == "prioridade":
            filtradas.sort(key=lambda r: (ordem[r["prioridade"]], r["score_geral"]), reverse=True)
        elif f.ordenar == "score":
            filtradas.sort(key=lambda r: r["score_geral"])
        else:
            filtradas.sort(key=lambda r: r["score_geral"], reverse=True)
        contagem = {
            c: sum(1 for r in linhas if passa(r, False) and r["categoria"] == c)
            for c in ("verde", "amarelo", "vermelho")
        }
        ini = (f.pagina - 1) * f.por_pagina
        return PaginaFila(filtradas[ini : ini + f.por_pagina], len(filtradas), contagem)

    def obter_item_fila(self, estudante_id: str) -> dict[str, Any] | None:
        self._check("obter_item_fila")
        return self._linha_fila(estudante_id) if estudante_id in self.estudantes else None

    def obter_score(self, score_id: str) -> dict[str, Any] | None:
        return self.scores.get(score_id)

    def serie_scores(self, estudante_id: str, limite: int) -> list[dict[str, Any]]:
        s = sorted(
            (x for x in self.scores.values() if x["estudante_id"] == estudante_id), key=lambda x: x["competencia"]
        )
        return s[-limite:]

    def ultima_validacao(self, caso_id: str) -> dict[str, Any] | None:
        vs = [v for v in self.validacoes if v["caso_id"] == caso_id]
        return vs[-1] if vs else None

    def registrar_validacao(self, d: dict[str, Any]) -> dict[str, Any]:
        """Mesma regra da RPC registrar_validacao_caso (migration 003)."""
        self._check("registrar_validacao")
        if d["estudante_id"] not in self.estudantes:
            raise RegistroNaoEncontrado("estudante")
        u = self._ultimo_score(d["estudante_id"])
        if not u:
            raise RegistroNaoEncontrado("score")
        if u["id"] != d["score_id"]:
            raise ConflitoVersao("score mudou")
        caso = next((c for c in self.casos.values() if c["estudante_id"] == d["estudante_id"]), None)
        if not caso:
            caso = {
                "id": str(uuid.uuid4()),
                "estudante_id": d["estudante_id"],
                "status": "novo",
                "prioridade": d.get("prioridade") or "media",
                "prazo": None,
                "atendente_responsavel": None,
                "score_atual_id": u["id"],
                "categoria_vigente": None,
            }
            self.casos[caso["id"]] = caso
            self._evento(caso["id"], d["atendente_id"], "criado", None, "novo")
        v = {
            "id": str(uuid.uuid4()),
            "caso_id": caso["id"],
            "score_id": u["id"],
            "atendente_id": d["atendente_id"],
            "decisao": d["decisao"],
            "justificativa": d["justificativa"],
            "categoria_ajustada": d.get("categoria_ajustada"),
            "prioridade_definida": d.get("prioridade"),
            "prazo_definido": d.get("prazo"),
            "versao_modelo": u["versao_modelo"],
            "criado_em": _agora(),
        }
        self.validacoes.append(v)
        status = d.get("status") or (
            "arquivado"
            if d["decisao"] == "rejeitado"
            else "em_acompanhamento"
            if caso["status"] == "novo"
            else caso["status"]
        )
        novo = {
            "status": status,
            "prioridade": d.get("prioridade") or caso["prioridade"],
            "prazo": d.get("prazo") or caso["prazo"],
            "atendente_responsavel": d["atendente_id"]
            if d.get("assumir_caso", True)
            else caso["atendente_responsavel"],
        }
        for campo, tipo in (
            ("status", "status"),
            ("prioridade", "prioridade"),
            ("prazo", "prazo"),
            ("atendente_responsavel", "responsavel"),
        ):
            if novo[campo] != caso[campo]:
                self._evento(caso["id"], d["atendente_id"], tipo, caso[campo], novo[campo])
        caso.update(novo)
        caso["categoria_vigente"] = {"ajustado": d.get("categoria_ajustada"), "rejeitado": "verde"}.get(d["decisao"])
        return {**v, "atendente_nome": self.perfis[d["atendente_id"]]["nome_completo"], "caso_status": status}

    def _evento(self, caso_id: str, uid: str | None, tipo: str, de: Any, para: Any) -> None:
        self.eventos.append(
            {
                "id": str(uuid.uuid4()),
                "caso_id": caso_id,
                "usuario_id": uid,
                "tipo": tipo,
                "de": None if de is None else str(de),
                "para": None if para is None else str(para),
                "detalhes": None,
                "criado_em": _agora(),
            }
        )

    def eventos_historico(self, estudante_id: str) -> dict[str, list[dict[str, Any]]]:
        caso = next((c for c in self.casos.values() if c["estudante_id"] == estudante_id), None)
        cid = caso["id"] if caso else None
        return {
            "scores": [s for s in self.scores.values() if s["estudante_id"] == estudante_id],
            "contatos": [c for c in self.contatos if c["estudante_id"] == estudante_id],
            "validacoes": [v for v in self.validacoes if v["caso_id"] == cid],
            "eventos": [e for e in self.eventos if e["caso_id"] == cid],
        }

    def estudante_existe(self, estudante_id: str) -> bool:
        return estudante_id in self.estudantes

    def features_recentes(self, estudante_id: str) -> dict[str, Any] | None:
        return self.features.get(estudante_id)

    def registrar_score(self, d: dict[str, Any]) -> str:
        sid = str(uuid.uuid4())
        self.scores[sid] = {
            "id": sid,
            **d,
            "competencia": date.fromisoformat(d["competencia"]),
            "calculado_em": _agora(),
        }
        return sid

    # --------------------------------------------------------------- admin
    def dashboard(self, de: date, ate: date) -> dict[str, Any]:
        self._check("dashboard")
        resp = list(self.respostas.values())
        abst = sum(1 for r in resp if r["abstencao"])
        dist = dict.fromkeys(("verde", "amarelo", "vermelho"), 0)
        for e in self.estudantes:
            if r := self._linha_fila(e):
                dist[r["categoria"]] += 1
        dec = {k: sum(1 for v in self.validacoes if v["decisao"] == k) for k in ("confirmado", "ajustado", "rejeitado")}
        return {
            "periodo": {"de": de, "ate": ate},
            "chat": {
                "conversas": len(self.conversas),
                "perguntas": len(resp),
                "estudantes_ativos": len({c["estudante_id"] for c in self.conversas.values()}),
                "taxa_abstencao": round(abst / len(resp), 4) if resp else 0,
                "confianca_media": None,
                "latencia_p95_ms": None,
                "latencia_media_ms": None,
                "feedback": {
                    "util": sum(1 for f in self.feedbacks if f["avaliacao"] == "util"),
                    "nao_util": sum(1 for f in self.feedbacks if f["avaliacao"] == "nao_util"),
                },
                "perguntas_por_dia": [],
                "principais_documentos": [],
            },
            "risco": {
                "distribuicao": dist,
                "distribuicao_mensal": [],
                "casos_por_status": {},
                "versao_modelo": "seed-sintetico-0",
            },
            "validacoes": {**dec, "tempo_medio_ate_validacao_horas": None},
            "encaminhamentos": {"abertos": len(self.encaminhamentos), "em_andamento": 0, "resolvidos": 0},
            "atualizado_em": _agora(),
        }

    def _resumo_doc(self, d: dict[str, Any]) -> dict[str, Any]:
        cs = [c for c in self.chunks_docs if c["documento_id"] == d["id"] and c["ativo"]]
        return {**d, "total_chunks": len(cs), "chunks_sem_embedding": sum(1 for c in cs if c["embedding"] is None)}

    def listar_documentos(
        self, busca: str | None, categoria: str | None, ativo: bool | None, pagina: int, por_pagina: int
    ) -> tuple[list[dict[str, Any]], int]:
        ds = [
            self._resumo_doc(d)
            for d in self.documentos.values()
            if (ativo is None or d["ativo"] == ativo) and (not categoria or d["categoria"] == categoria)
        ]
        return ds[(pagina - 1) * por_pagina : pagina * por_pagina], len(ds)

    def obter_documento(self, documento_id: str) -> dict[str, Any] | None:
        d = self.documentos.get(documento_id)
        if not d:
            return None
        vs = sorted((v for v in self.versoes if v["documento_id"] == documento_id), key=lambda v: -v["versao"])
        return {
            **self._resumo_doc(d),
            "conteudo": vs[0]["conteudo"],
            "versoes": [
                {
                    "versao": v["versao"],
                    "data_atualizacao": v["data_atualizacao"],
                    "motivo": v["motivo"],
                    "alterado_por": self.perfis.get(v["alterado_por"], {}).get("nome_completo"),
                    "criado_em": v["criado_em"],
                }
                for v in vs
            ],
        }

    def _gravar_chunks(self, did: str, chunks: list[dict[str, Any]]) -> None:
        for c in self.chunks_docs:
            if c["documento_id"] == did:
                c["ativo"], c["embedding"] = False, None
        for c in chunks:
            self.chunks_docs.append(
                {"documento_id": did, "conteudo": c["conteudo"], "embedding": c["embedding"], "ativo": True}
            )

    def criar_documento(self, d: dict[str, Any]) -> str:
        self._check("criar_documento")
        did = str(uuid.uuid4())
        self.documentos[did] = {
            "id": did,
            "titulo": d["titulo"],
            "categoria": d["categoria"],
            "fonte": d["fonte"],
            "versao": 1,
            "ativo": True,
            "data_atualizacao": d["data_atualizacao"],
            "desativado_em": None,
            "motivo_desativacao": None,
        }
        self.versoes.append(
            {
                "documento_id": did,
                "versao": 1,
                "conteudo": d["conteudo"],
                "data_atualizacao": d["data_atualizacao"],
                "motivo": "Cadastro inicial",
                "alterado_por": d["usuario_id"],
                "criado_em": _agora(),
            }
        )
        self._gravar_chunks(did, d["chunks"])
        return did

    def nova_versao_documento(self, d: dict[str, Any]) -> None:
        doc = self.documentos.get(d["documento_id"])
        if not doc:
            raise RegistroNaoEncontrado("doc")
        if doc["versao"] != d["versao_base"]:
            raise ConflitoVersao("versão")
        doc["versao"] += 1
        doc["data_atualizacao"] = d["data_atualizacao"]
        for k in ("titulo", "categoria", "fonte"):
            if d.get(k):
                doc[k] = d[k]
        self.versoes.append(
            {
                "documento_id": doc["id"],
                "versao": doc["versao"],
                "conteudo": d["conteudo"],
                "data_atualizacao": d["data_atualizacao"],
                "motivo": d["motivo"],
                "alterado_por": d["usuario_id"],
                "criado_em": _agora(),
            }
        )
        self._gravar_chunks(doc["id"], d["chunks"])

    def desativar_documento(self, documento_id: str, motivo: str, usuario_id: str) -> None:
        doc = self.documentos.get(documento_id)
        if not doc:
            raise RegistroNaoEncontrado("doc")
        if not doc["ativo"]:
            raise ConflitoVersao("já desativado")
        doc.update(ativo=False, desativado_em=_agora(), motivo_desativacao=motivo)

    # --------------------------------------------------------------- auditoria
    def registrar_auditoria(self, registro: dict[str, Any]) -> None:
        self._check("registrar_auditoria")
        self.auditoria.append(registro)
