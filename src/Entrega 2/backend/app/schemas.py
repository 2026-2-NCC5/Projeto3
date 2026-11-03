"""Modelos Pydantic espelhando docs/api-contract.yaml (v0.9.0). Nomes iguais ao contrato."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Papel = Literal["estudante", "atendente", "administrador", "equipe_tecnica"]
Categoria = Literal["verde", "amarelo", "vermelho"]
Prioridade = Literal["baixa", "media", "alta", "urgente"]
StatusCaso = Literal["novo", "em_acompanhamento", "contatado", "resolvido", "arquivado"]
Decisao = Literal["confirmado", "ajustado", "rejeitado"]
Dimensao = Literal["financeira", "academica", "relacionamento"]
Tendencia = Literal["subindo", "estavel", "caindo"]
FaixaDistancia = Literal["ate_5km", "5_15km", "15_30km", "acima_30km"]
Probabilidade = Field(ge=0, le=1)


class Modelo(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Paginacao(Modelo):
    total: int
    pagina: int
    por_pagina: int


class UsuarioRef(Modelo):
    id: UUID
    nome: str


# ------------------------------------------------------------------ operação
class DependenciaSaude(Modelo):
    status: Literal["ok", "falha"]
    latencia_ms: int | None = None


class Saude(Modelo):
    status: Literal["ok", "degradado"]
    versao: str
    versao_modelo_risco: str | None
    dependencias: dict[str, DependenciaSaude]
    verificado_em: datetime


class EstudanteMe(Modelo):
    id: UUID
    ra: str
    curso: str
    semestre: int


class Me(Modelo):
    id: UUID
    nome: str
    email: str
    papel: Papel
    estudante: EstudanteMe | None = None


# ------------------------------------------------------------------ chat
class MensagemHistorico(Modelo):
    papel: Literal["estudante", "agente"]
    conteudo: str = Field(max_length=2000)


class ChatPergunta(Modelo):
    mensagem: str = Field(min_length=1, max_length=1000)
    conversa_id: UUID | None = None
    historico: list[MensagemHistorico] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def _nao_vazia(self) -> ChatPergunta:
        if not self.mensagem.strip():
            raise ValueError("Escreva sua pergunta.")
        return self


class Fonte(Modelo):
    documento_id: UUID | None = None
    titulo: str
    fonte: str
    data_atualizacao: datetime
    trecho: str
    similaridade: float | None = Field(default=None, ge=0, le=1)


class Encaminhamento(Modelo):
    id: UUID
    status: Literal["aberto", "em_andamento", "resolvido"]
    setor_destino: str
    prazo: datetime | None = None


class ChatResposta(Modelo):
    resposta: str
    fontes: list[Fonte]
    confianca: float = Probabilidade
    abstencao: bool
    motivo_abstencao: (
        Literal["baixa_similaridade", "sem_documentos", "falha_vetorizacao", "falha_busca", "fora_do_escopo"] | None
    ) = None
    encaminhamento: Encaminhamento | None = None
    resposta_id: UUID
    conversa_id: UUID
    versao_modelo: str
    gerada_em: datetime


class ConversaResumo(Modelo):
    id: UUID
    titulo: str
    status: Literal["aberta", "encerrada", "encaminhada_humano"]
    iniciada_em: datetime
    atualizada_em: datetime
    ultima_mensagem: str | None = Field(default=None, max_length=140)


class PaginaConversas(Paginacao):
    itens: list[ConversaResumo]


class RespostaMensagem(Modelo):
    resposta_id: UUID
    fontes: list[Fonte]
    confianca: float = Probabilidade
    abstencao: bool
    feedback: Literal["util", "nao_util"] | None = None


class MensagemConversa(Modelo):
    id: UUID
    remetente: Literal["estudante", "agente", "atendente"]
    conteudo: str
    criado_em: datetime
    resposta: RespostaMensagem | None = None


class ConversaDetalhe(ConversaResumo):
    mensagens: list[MensagemConversa]
    encaminhamento: Encaminhamento | None = None


class FeedbackEntrada(Modelo):
    resposta_id: UUID
    avaliacao: Literal["util", "nao_util"]
    comentario: str | None = Field(default=None, max_length=500)


class Feedback(FeedbackEntrada):
    id: UUID
    criado_em: datetime


# ------------------------------------------------------------------ casos
class EstudanteResumo(Modelo):
    id: UUID
    ra: str
    nome: str
    curso: str
    semestre: int
    faixa_distancia: FaixaDistancia | None = None
    regiao: str | None = None


class ResumoCaso(Modelo):
    estudante: EstudanteResumo
    caso_id: UUID | None = None
    score_geral: float = Probabilidade
    categoria: Categoria
    categoria_modelo: Categoria
    tendencia: Tendencia
    variacao: float | None = None
    status: StatusCaso | None
    prioridade: Prioridade | None
    prazo: date | None = None
    responsavel: UsuarioRef | None = None
    ultima_decisao: Decisao | None = None
    versao_modelo: str
    atualizado_em: datetime


class ContagemCategorias(Modelo):
    verde: int
    amarelo: int
    vermelho: int


class PaginaCasos(Paginacao):
    itens: list[ResumoCaso]
    contagem: ContagemCategorias


class Fator(Modelo):
    codigo: str
    descricao: str
    dimensao: Dimensao
    direcao: Literal["aumenta", "reduz"]
    peso: float = Field(ge=0, le=1)


class Score(Modelo):
    geral: float = Probabilidade
    financeiro: float = Probabilidade
    academico: float = Probabilidade
    relacionamento: float = Probabilidade


class PontoTendencia(Modelo):
    competencia: date
    score_geral: float = Probabilidade
    categoria: Categoria


class CasoSituacao(Modelo):
    id: UUID | None = None
    status: StatusCaso
    prioridade: Prioridade
    prazo: date | None = None
    responsavel: UsuarioRef | None = None


class Validacao(Modelo):
    id: UUID
    score_id: UUID | None = None
    decisao: Decisao
    justificativa: str
    categoria_ajustada: Categoria | None = None
    prioridade: Prioridade | None = None
    prazo: date | None = None
    atendente: UsuarioRef
    versao_modelo: str
    criado_em: datetime


AVISO_APOIO = "Apoio à decisão. Nenhuma ação deve ser tomada sem avaliação humana."


class CasoDetalhe(Modelo):
    estudante: EstudanteResumo
    score_id: UUID
    score: Score
    categoria: Categoria
    categoria_modelo: Categoria
    fatores: list[Fator] = Field(max_length=8)
    tendencia: list[PontoTendencia]
    recomendacao: str
    caso: CasoSituacao
    ultima_validacao: Validacao | None = None
    versao_modelo: str
    atualizado_em: datetime
    aviso: Literal["Apoio à decisão. Nenhuma ação deve ser tomada sem avaliação humana."] = AVISO_APOIO


class ValidacaoEntrada(Modelo):
    score_id: UUID
    decisao: Decisao
    justificativa: str = Field(min_length=20, max_length=2000)
    categoria_ajustada: Categoria | None = None
    prioridade: Prioridade | None = None
    prazo: date | None = None
    status: StatusCaso | None = None
    assumir_caso: bool = True

    @model_validator(mode="after")
    def _regras(self) -> ValidacaoEntrada:
        if len(self.justificativa.strip()) < 20:
            raise ValueError("Escreva pelo menos 20 caracteres na justificativa.")
        if self.decisao == "ajustado" and self.categoria_ajustada is None:
            raise ValueError("Informe a categoria ajustada.")
        return self


class EventoHistorico(Modelo):
    id: UUID
    tipo: Literal["score", "validacao", "contato", "status", "prioridade", "prazo", "responsavel", "criado"]
    ocorrido_em: datetime
    descricao: str
    usuario: UsuarioRef | None = None
    dados: dict[str, Any] = Field(default_factory=dict)


class PaginaHistorico(Paginacao):
    itens: list[EventoHistorico]


# ------------------------------------------------------------------ risco
class FeaturesRisco(Modelo):
    tempo_de_curso: float = Field(ge=0)
    idade: int | None = Field(default=None, ge=14, le=100)
    mora_sp_capital: bool | None = None
    total_parcelas: int = Field(ge=0)
    pct_parcelas_em_aberto: float = Field(ge=0, le=1)
    pct_parcelas_acordo: float = Field(ge=0, le=1)
    atraso_medio_dias: float
    valor_total_periodo: float | None = Field(default=None, ge=0)
    media_notas: float = Field(ge=0, le=100)
    media_assiduidade: float = Field(ge=0, le=100)
    pct_reprovacao: float = Field(ge=0, le=1)
    tendencia_notas: float | None = None
    tendencia_assiduidade: float | None = None
    total_semestres: int = Field(ge=0)
    total_contatos: int | None = Field(default=None, ge=0)
    dias_desde_ultimo_contato: int | None = Field(default=None, ge=0)
    forma_ingresso: str | None = None
    grau_academico: str | None = None
    turno: str | None = None
    estado_civil: str | None = None
    sexo: str | None = None
    tem_bolsa: bool | None = None


class InferenciaEntrada(Modelo):
    estudante_id: UUID | None = None
    features: FeaturesRisco | None = None
    persistir: bool = False

    @model_validator(mode="after")
    def _um_dos_dois(self) -> InferenciaEntrada:
        if (self.estudante_id is None) == (self.features is None):
            raise ValueError("Informe estudante_id ou features (apenas um dos dois).")
        if self.persistir and self.estudante_id is None:
            raise ValueError("persistir exige estudante_id.")
        return self


class InferenciaResultado(Modelo):
    probabilidade: float = Probabilidade
    categoria: Categoria
    score: Score
    fatores: list[Fator]
    recomendacao: str | None = None
    versao_modelo: str
    calculado_em: datetime
    persistido: bool = False
    score_id: UUID | None = None


class Limiares(Modelo):
    amarelo: float
    vermelho: float


class ModeloInfo(Modelo):
    versao: str
    algoritmo: str
    treinado_em: datetime
    limiares: Limiares
    metricas: dict[str, float]
    features: list[str] = Field(default_factory=list)


# ------------------------------------------------------------------ admin
class Periodo(Modelo):
    de: date
    ate: date


class Feedbacks(Modelo):
    util: int
    nao_util: int


class PerguntasDia(Modelo):
    dia: date
    total: int
    abstencoes: int


class DocumentoCitado(Modelo):
    documento_id: UUID | None = None
    titulo: str
    citacoes: int


class DashboardChat(Modelo):
    conversas: int
    perguntas: int
    estudantes_ativos: int
    taxa_abstencao: float = Probabilidade
    confianca_media: float | None = Field(default=None, ge=0, le=1)
    latencia_p95_ms: int | None = None
    latencia_media_ms: int | None = None  # extra (não está no contrato; aditivo)
    feedback: Feedbacks
    perguntas_por_dia: list[PerguntasDia] = Field(default_factory=list)
    principais_documentos: list[DocumentoCitado] = Field(default_factory=list, max_length=10)


class DistribuicaoMensal(ContagemCategorias):
    competencia: date


class DashboardRisco(Modelo):
    distribuicao: ContagemCategorias
    distribuicao_mensal: list[DistribuicaoMensal] = Field(default_factory=list)
    casos_por_status: dict[str, int] = Field(default_factory=dict)
    versao_modelo: str


class DashboardValidacoes(Modelo):
    confirmado: int
    ajustado: int
    rejeitado: int
    tempo_medio_ate_validacao_horas: float | None = None


class DashboardEncaminhamentos(Modelo):
    abertos: int
    em_andamento: int
    resolvidos: int


class Dashboard(Modelo):
    periodo: Periodo
    chat: DashboardChat
    risco: DashboardRisco
    validacoes: DashboardValidacoes
    encaminhamentos: DashboardEncaminhamentos
    atualizado_em: datetime


class DocumentoResumo(Modelo):
    id: UUID
    titulo: str
    categoria: str
    fonte: str
    versao: int = Field(ge=1)
    ativo: bool
    data_atualizacao: datetime
    total_chunks: int
    chunks_sem_embedding: int | None = None


class PaginaDocumentos(Paginacao):
    itens: list[DocumentoResumo]


class DocumentoEntrada(Modelo):
    titulo: str = Field(min_length=3, max_length=200)
    categoria: str = Field(min_length=2, max_length=60)
    fonte: str = Field(min_length=3, max_length=300)
    conteudo: str = Field(min_length=20, max_length=100_000)
    data_atualizacao: datetime | None = None


class NovaVersaoEntrada(Modelo):
    versao_base: int = Field(ge=1)
    titulo: str | None = Field(default=None, min_length=3, max_length=200)
    categoria: str | None = None
    fonte: str | None = None
    conteudo: str = Field(min_length=20, max_length=100_000)
    motivo: str = Field(min_length=10, max_length=500)
    data_atualizacao: datetime | None = None


class DesativarEntrada(Modelo):
    motivo: str = Field(min_length=10, max_length=500)


class VersaoDocumento(Modelo):
    versao: int
    data_atualizacao: datetime
    motivo: str | None = None
    alterado_por: str | None = None
    criado_em: datetime


class DocumentoDetalhe(DocumentoResumo):
    conteudo: str
    desativado_em: datetime | None = None
    motivo_desativacao: str | None = None
    versoes: list[VersaoDocumento]
