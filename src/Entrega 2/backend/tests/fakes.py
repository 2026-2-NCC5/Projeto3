"""Dublês de teste: repositório em memória, provedores de embedding e emissor de JWT."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, date, datetime
from typing import Any

import jwt

from app.db.memoria import RepoMemoria as _RepoMemoriaBase
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
def _chunk(cid: str, did: str, titulo: str, conteudo: str) -> dict[str, Any]:
    return {
        "chunk_id": cid,
        "documento_id": did,
        "conteudo": conteudo,
        "titulo_documento": titulo,
        "fonte_documento": f"Cesta de Serviços ASA - {titulo}",
        "data_atualizacao": "2026-10-15T00:00:00+00:00",
    }


class RepoMemoria(_RepoMemoriaBase):
    """Repositório em memória semeado com o mínimo que os testes usam."""

    def __init__(self) -> None:
        super().__init__()
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
