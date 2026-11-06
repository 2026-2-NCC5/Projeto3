"""Módulo de recuperação (funções puras): reescrita, decisão de abstenção, resposta extrativa."""

from __future__ import annotations

import pytest

from app.rag import (
    ConfigRAG,
    FalhaBusca,
    IndiceLexical,
    Mensagem,
    Vetorizacao,
    compor_resposta,
    dividir_em_chunks,
    eh_continuacao,
    recuperar,
    reescrever_pergunta,
)
from app.rag.resposta import TEXTO_ABSTENCAO, TEXTO_FALHA, formatar_passos
from tests.fakes import CHUNK_ATESTADO, CHUNK_ATESTADO_LOCAL, CHUNK_TRANCAMENTO, RepoMemoria

HIST = [
    Mensagem("estudante", "Como faço o trancamento de matrícula?"),
    Mensagem("agente", "O trancamento é solicitado pelo Portal do Aluno."),
]


def _vet(_: str) -> Vetorizacao:
    return Vetorizacao([1.0, 0.0], "cloudflare", "@cf/baai/bge-m3", 5)


def _busca(linhas):
    return lambda _v, k: linhas[:k]


# ------------------------------------------------------------------ reescrita
@pytest.mark.parametrize("pergunta", ["e o prazo?", "E quanto custa?", "isso vale para EAD?", "prazo", "e depois?"])
def test_continuacao_e_reescrita_com_o_assunto_anterior(pergunta):
    r = reescrever_pergunta(pergunta, HIST)
    assert r.reescrita
    assert "trancamento de matrícula" in r.consulta
    assert r.base == "Como faço o trancamento de matrícula?"


@pytest.mark.parametrize("pergunta", ["Como emito o boleto da mensalidade?", "Qual o horário da biblioteca?"])
def test_pergunta_completa_nao_e_reescrita(pergunta):
    r = reescrever_pergunta(pergunta, HIST)
    assert not r.reescrita and r.consulta == pergunta


def test_sem_historico_nao_reescreve():
    assert not reescrever_pergunta("e o prazo?", []).reescrita


def test_continuacao_em_cadeia_sobe_ate_a_pergunta_com_assunto():
    hist = [
        Mensagem("estudante", "Como faço o trancamento de matrícula?"),
        Mensagem("agente", "..."),
        Mensagem("estudante", "e o prazo?"),
        Mensagem("agente", "..."),
    ]
    r = reescrever_pergunta("e pra EAD?", hist)
    assert "trancamento" in r.consulta and "prazo" in r.consulta and "EAD" in r.consulta


def test_eh_continuacao():
    assert eh_continuacao("e o prazo?")
    assert not eh_continuacao("Como faço para pedir bolsa de estudos?")


# ------------------------------------------------------------------ decisão
def test_acima_do_limiar_responde_com_fontes():
    repo = RepoMemoria()
    linhas = [repo.resultado(CHUNK_ATESTADO, 0.71), repo.resultado(CHUNK_ATESTADO_LOCAL, 0.6)]
    r = recuperar("Como tiro o atestado?", vetorizar=_vet, buscar_vetorial=_busca(linhas))
    assert not r.abstencao and r.metodo == "vetorial"
    assert r.confianca == 0.71 and r.trechos[0].titulo == "Atestado de matrícula"


@pytest.mark.parametrize("sim", [0.0, 0.3, 0.5499])
def test_abaixo_do_limiar_se_abstem(sim):
    repo = RepoMemoria()
    r = recuperar(
        "Posso levar meu cachorro?",
        vetorizar=_vet,
        buscar_vetorial=_busca([repo.resultado(CHUNK_ATESTADO, sim)]),
        config=ConfigRAG(limiar=0.55),
    )
    assert r.abstencao and r.motivo_abstencao == "baixa_similaridade"
    assert r.trechos  # candidatos fracos continuam disponíveis para "fontes"
    texto, usados = compor_resposta(r)
    assert texto == TEXTO_ABSTENCAO and usados == []


def test_limiar_configuravel():
    repo = RepoMemoria()
    linhas = [repo.resultado(CHUNK_ATESTADO, 0.6)]
    assert recuperar("x", vetorizar=_vet, buscar_vetorial=_busca(linhas), config=ConfigRAG(limiar=0.65)).abstencao
    assert not recuperar("x", vetorizar=_vet, buscar_vetorial=_busca(linhas), config=ConfigRAG(limiar=0.5)).abstencao


def test_sem_documentos_se_abstem():
    r = recuperar("x", vetorizar=_vet, buscar_vetorial=_busca([]))
    assert r.abstencao and r.motivo_abstencao == "sem_documentos"


def test_falha_na_busca_sem_fallback_se_abstem():
    def busca_quebrada(_v, _k):
        raise FalhaBusca("timeout")

    r = recuperar("x", vetorizar=_vet, buscar_vetorial=busca_quebrada, config=ConfigRAG(fallback_lexical=False))
    assert r.abstencao and r.motivo_abstencao == "falha_busca" and r.metodo == "nenhum"
    assert compor_resposta(r)[0] == TEXTO_FALHA


def test_consulta_reescrita_e_a_que_vai_para_a_vetorizacao():
    vistas = []

    def vet(texto):
        vistas.append(texto)
        return _vet(texto)

    recuperar("e o prazo?", HIST, vetorizar=vet, buscar_vetorial=_busca([]))
    assert "trancamento" in vistas[0] and "prazo" in vistas[0]


# ------------------------------------------------------------------ resposta extrativa
def test_resposta_usa_somente_o_conteudo_recuperado():
    repo = RepoMemoria()
    linhas = [
        repo.resultado(CHUNK_ATESTADO, 0.71),
        repo.resultado(CHUNK_ATESTADO_LOCAL, 0.62),
        repo.resultado(CHUNK_TRANCAMENTO, 0.6),
    ]
    r = recuperar("Como tiro o atestado?", vetorizar=_vet, buscar_vetorial=_busca(linhas))
    texto, usados = compor_resposta(r)
    # complementa com trechos do MESMO documento acima do limiar; não mistura documentos
    assert [t.chunk_id for t in usados] == [CHUNK_ATESTADO, CHUNK_ATESTADO_LOCAL]
    corpus = " ".join(t.conteudo for t in usados)
    for palavra in texto.replace("\n", " ").split():
        assert palavra in corpus  # nenhuma palavra fora dos trechos oficiais


def test_enumeracao_vira_passos_numerados():
    t = formatar_passos("Condições: 1) Estar formado; 2) Pedir antes da colação")
    assert t == "Condições:\n1. Estar formado\n2. Pedir antes da colação"


# ------------------------------------------------------------------ índice lexical e chunks
def test_indice_lexical_acha_o_documento_certo():
    idx = IndiceLexical.construir(RepoMemoria().chunks)
    (meta, sim), *_ = idx.buscar("como tirar atestado de matrícula", 2)
    assert meta["titulo_documento"] == "Atestado de matrícula" and 0 < sim <= 1
    assert idx.buscar("receita de bolo de cenoura") == []


def test_dividir_em_chunks_respeita_tamanho_e_prefixa_titulo():
    texto = "\n\n".join(f"Parágrafo {i}. " + "texto " * 60 for i in range(6))
    chunks = dividir_em_chunks(texto, "Regulamento")
    assert len(chunks) > 1
    assert all(c.startswith("Regulamento: ") for c in chunks)
    assert all(len(c) <= 1100 for c in chunks)
