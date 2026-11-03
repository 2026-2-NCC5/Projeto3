"""Testes da recuperação local e do verificador de groundedness (sem baixar modelos)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ML = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML))

from rag.groundedness import verificar
from rag.recuperacao import Recuperador, TfidfHashing, carregar_corpus, montar_consulta

CAMPOS_RPC = {"chunk_id", "documento_id", "conteudo", "similaridade", "titulo_documento", "fonte_documento", "data_atualizacao"}


def test_corpus_ficticio_tem_20_documentos() -> None:
    chunks = carregar_corpus()
    assert len({c.documento_id for c in chunks}) == 20


def test_busca_no_formato_da_rpc() -> None:
    rec = Recuperador(TfidfHashing(usar_idf=True))
    out = rec.buscar("Qual o prazo para trancar a matrícula?")
    assert len(out) == 3 and set(out[0]) == CAMPOS_RPC
    assert out[0]["titulo_documento"] == "Trancamento de Matrícula"
    assert out[0]["similaridade"] >= out[1]["similaridade"]


def test_resposta_no_formato_do_perguntar_py_e_abstencao() -> None:
    rec = Recuperador(TfidfHashing(usar_idf=True))
    ok = rec.processar_pergunta("Quantos livros posso pegar na biblioteca?", limiar=0.19)
    assert set(ok) == {"resposta", "confianca", "abstencao", "evidencias"} and not ok["abstencao"]
    assert {"titulo", "fonte", "similaridade", "atualizado_em", "trecho"} == set(ok["evidencias"][0])
    fora = rec.processar_pergunta("Me passa uma receita de bolo de cenoura", limiar=0.19)
    assert fora["abstencao"] and "atendente" in fora["resposta"]


def test_contexto_entra_na_consulta() -> None:
    assert montar_consulta("E por quanto tempo?", ["Quantos livros posso pegar?"]) == "Quantos livros posso pegar? E por quanto tempo?"


def test_groundedness_pega_prazo_trocado_e_frase_inventada() -> None:
    trecho = "O pedido de revisão de nota deve ser feito em até 5 dias úteis após a divulgação do resultado."
    assert verificar(trecho, [trecho])["fundamentada"]
    assert not verificar(trecho.replace("5", "10"), [trecho])["fundamentada"]
    assert not verificar(trecho + " Também é possível pedir pelo WhatsApp da reitoria.", [trecho])["fundamentada"]


def test_conjunto_de_perguntas() -> None:
    linhas = [json.loads(x) for x in (ML / "rag_eval" / "perguntas.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(linhas) == 60
    docs = {c.documento_id for c in carregar_corpus()}
    for p in linhas:
        assert set(p["documentos_esperados"]) <= docs
        assert (p["tipo"].startswith("fora_escopo")) == (not p["documentos_esperados"])
