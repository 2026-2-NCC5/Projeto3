"""Repositório do modo de demonstração (DEMO_MODE=true).

Carrega `seeds/demo_snapshot.json.gz` (exportado do banco local montado só com
`seeds/`: estudantes fictícios + base oficial pública) num `RepoMemoria`.
Não depende de rede: serve para apresentar o produto sem Supabase.

Por cima dos seeds, faz duas curadorias determinísticas, para a demo contar
uma história clara (nada disso altera score, fator ou recomendação do modelo):
- 3 casos vermelhos com histórias diferentes (notas, inadimplência, frequência)
  ficam no topo da fila, como "novos" e sem atendente;
- um histórico de uso do chat dos últimos 30 dias (simulado, marcado como
  `sintetico`) para o painel da administração não abrir zerado.

`reiniciar()` volta tudo ao estado inicial (scripts/reset_demo.sh).
"""

from __future__ import annotations

import gzip
import json
import random
import threading
import uuid
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any

from app.db.memoria import RepoMemoria, _agora

# Histórias da fila: grupo de fatores do modelo -> rótulo (só para o log/README)
HISTORIAS: list[tuple[str, frozenset[str]]] = [
    ("queda de notas", frozenset({"media_notas", "tendencia_notas", "reprovacoes"})),
    ("inadimplência", frozenset({"parcelas_em_aberto", "atraso_pagamentos"})),
    ("sumiço das aulas", frozenset({"frequencia", "tendencia_frequencia"})),
]

# Temas mais procurados no chat simulado (busca por trecho do título na base oficial)
TEMAS_CHAT = [
    ("trancamento de matrícula", 9),
    ("atestado de matrícula", 8),
    ("rematrícula", 6),
    ("estágio obrigatório", 5),
    ("prova substitutiva", 5),
    ("cadastro de atividade complementar", 4),
    ("aproveitamento de disciplinas", 4),
    ("solicitação de boleto", 4),
    ("cancelamento de matrícula", 3),
    ("transferência de turno", 2),
]


def _dt(v: Any) -> datetime | None:
    if v is None or isinstance(v, datetime):
        return v
    d = datetime.fromisoformat(str(v))
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _d(v: Any) -> date | None:
    if v is None or isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


class RepoDemo(RepoMemoria):
    def __init__(self, caminho_snapshot: Path, hoje: date | None = None, modelo: Any = None) -> None:
        super().__init__()
        self._caminho = caminho_snapshot
        self._modelo = modelo
        self._hoje = hoje
        self._trava = threading.RLock()
        self.historias: list[dict[str, Any]] = []
        self.reiniciar()

    # ------------------------------------------------------------------ carga
    def reiniciar(self) -> None:
        with gzip.open(self._caminho, "rt", encoding="utf-8") as f:
            snap = json.load(f)
        with self._trava:
            RepoMemoria.__init__(self)
            self.historias = []
            self._carregar(snap)
            self._curar_historias()
            self._simular_uso_chat()

    def _carregar(self, s: dict[str, list[dict[str, Any]]]) -> None:
        # Trajetórias pré-calculadas pelo modelo real (seeds/curar_snapshot_demo.py)
        for sc in s.get("curadoria_scores", []):
            alvo = next((x for x in s["scores_risco"] if x["id"] == sc["id"]), None)
            if alvo:
                alvo.update(sc)
        self.perfis = {p["id"]: p for p in s["perfis"]}
        self.estudantes = {e["id"]: e for e in s["estudantes"]}
        for sc in s["scores_risco"]:
            sc["competencia"] = _d(sc["competencia"])
            sc["calculado_em"] = _dt(sc["calculado_em"])
            for k in ("probabilidade", "score_financeiro", "score_academico", "score_relacionamento"):
                sc[k] = float(sc[k]) if sc[k] is not None else None
            self.scores[sc["id"]] = sc
        for c in s["casos_risco"]:
            c["prazo"] = _d(c["prazo"])
            c["criado_em"] = _dt(c["criado_em"])
            self.casos[c["id"]] = c
        for v in s["validacoes_caso"]:
            v["criado_em"] = _dt(v["criado_em"])
            v["prazo_definido"] = _d(v["prazo_definido"])
        self.validacoes = sorted(s["validacoes_caso"], key=lambda v: v["criado_em"])
        for e in s["eventos_caso"]:
            e["criado_em"] = _dt(e["criado_em"])
        self.eventos = sorted(s["eventos_caso"], key=lambda e: e["criado_em"])
        for c in s["contatos_asa"]:
            c["ocorrido_em"] = _dt(c["ocorrido_em"])
        self.contatos = s["contatos_asa"]
        for f in sorted(s["estudante_features"], key=lambda f: f["competencia"]):
            f["competencia"] = _d(f["competencia"])
            self.features[f["estudante_id"]] = f  # fica a competência mais recente

        # ---- base de conhecimento
        for d in s["documentos_oficiais"]:
            d["data_atualizacao"] = _dt(d["data_atualizacao"])
            self.documentos[d["id"]] = d
        self.versoes = [
            {**v, "data_atualizacao": _dt(v["data_atualizacao"]), "criado_em": _dt(v["criado_em"])}
            for v in s["documentos_versoes"]
        ]
        self.chunks_docs = [
            {
                "chunk_id": c["id"],
                "documento_id": c["documento_id"],
                "ordem": c["ordem"],
                "conteudo": c["conteudo"],
                "embedding": None,
                "ativo": c["ativo"],
            }
            for c in sorted(s["documentos_chunks"], key=lambda c: (c["documento_id"], c["ordem"]))
        ]
        self._sincronizar_chunks()

        # ---- chat do estudante demo
        for c in s["conversas"]:
            c["iniciada_em"], c["atualizado_em"] = _dt(c["iniciada_em"]), _dt(c["atualizado_em"])
            self.conversas[c["id"]] = c
        for m in s["mensagens"]:
            m["criado_em"] = _dt(m["criado_em"])
        self.mensagens = sorted(s["mensagens"], key=lambda m: m["criado_em"])
        conversa_da_msg = {m["id"]: m["conversa_id"] for m in self.mensagens}
        for r in s["respostas_agente"]:
            self.respostas[r["id"]] = {
                "id": r["id"],
                "mensagem_id": r["mensagem_id"],
                "conversa_id": conversa_da_msg.get(r["mensagem_id"]),
                "confianca": float(r["confianca_score"] or 0),
                "abstencao": r["abstencao"],
                "latencia_ms": r["latencia_ms"],
                "versao_modelo": r["versao_modelo"],
                "criado_em": _dt(r["criado_em"]),
                "evidencias": [
                    {"chunk_id": e["chunk_id"], "similaridade": float(e["similaridade"])}
                    for e in sorted(s["resposta_evidencias"], key=lambda e: e["posicao_ranking"])
                    if e["resposta_id"] == r["id"]
                ],
            }
        self.feedbacks = [{**f, "criado_em": _dt(f["criado_em"])} for f in s["feedback_respostas"]]
        self.encaminhamentos = [{**e, "prazo": _dt(e["prazo"])} for e in s["encaminhamentos"]]

    @property
    def hoje(self) -> date:
        return self._hoje or datetime.now(UTC).date()

    # ------------------------------------------------------------------ curadoria
    def _curar_historias(self) -> None:
        """Escolhe 3 vermelhos de outubro com tendência de alta, um por história."""
        por_estudante: dict[str, list[dict[str, Any]]] = {}
        for sc in self.scores.values():
            por_estudante.setdefault(sc["estudante_id"], []).append(sc)
        caso_de = {c["estudante_id"]: c for c in self.casos.values()}

        candidatos = []
        for eid, serie in por_estudante.items():
            serie.sort(key=lambda x: x["competencia"])
            ult = serie[-1]
            if ult["categoria"] != "vermelho" or eid not in caso_de or len(serie) < 3:
                continue
            fatores = sorted(
                (f for f in ult["fatores"] or [] if f.get("direcao") == "aumenta"), key=lambda f: -f["peso"]
            )
            if not fatores:
                continue
            subida_mes = ult["probabilidade"] - serie[-2]["probabilidade"]
            subida_total = ult["probabilidade"] - serie[0]["probabilidade"]
            for f in fatores[:2]:
                candidatos.append((eid, f["codigo"], subida_mes, subida_total))

        escolhidos: list[str] = []
        for rotulo, codigos in HISTORIAS:
            opcoes = [c for c in candidatos if c[1] in codigos and c[0] not in escolhidos and c[3] > 0]
            # tendência visível: sobe no último mês (>= 5 p.p., o "subindo" da fila) e no semestre
            opcoes.sort(key=lambda c: (c[2] >= 0.05, c[3]), reverse=True)
            if opcoes and opcoes[0][2] >= 0.05:
                eid, fator = opcoes[0][0], opcoes[0][1]
            elif (gerado := self._trajetoria_pontuada(codigos, set(escolhidos))) is not None:
                eid, fator = gerado
            elif opcoes:
                eid, fator = opcoes[0][0], opcoes[0][1]
            else:
                continue
            escolhidos.append(eid)
            self.historias.append({"estudante_id": eid, "historia": rotulo, "fator_principal": fator})

        if not escolhidos:
            return
        # Os 3 ficam sozinhos como "urgente": os demais urgentes do seed viram "alta".
        for c in self.casos.values():
            if c["prioridade"] == "urgente" and c["estudante_id"] not in escolhidos:
                c["prioridade"] = "alta"
        for i, eid in enumerate(escolhidos):
            caso = caso_de[eid]
            self.validacoes = [v for v in self.validacoes if v["caso_id"] != caso["id"]]
            self.eventos = [e for e in self.eventos if e["caso_id"] != caso["id"] or e["tipo"] == "criado"]
            caso.update(
                status="novo",
                prioridade="urgente",
                atendente_responsavel=None,
                categoria_vigente=None,
                prazo=self.hoje + timedelta(days=2 + i),
            )
            if not any(e["caso_id"] == caso["id"] for e in self.eventos):
                self.eventos.insert(
                    0,
                    {
                        "id": str(uuid.uuid4()),
                        "caso_id": caso["id"],
                        "usuario_id": None,
                        "tipo": "criado",
                        "de": None,
                        "para": "novo",
                        "detalhes": {"origem": "modelo"},
                        "criado_em": caso.get("criado_em") or _agora(),
                    },
                )

    def _trajetoria_pontuada(self, codigos: frozenset[str], evitar: set[str]) -> tuple[str, str] | None:
        """Para a história de inadimplência: os seeds não trazem um vermelho com alta recente.
        Para cada estudante com caso aberto, faz as parcelas em aberto e o atraso crescerem de
        maio a outubro e pontua CADA mês com o modelo real (score, fatores e recomendação são
        os do modelo, como em seeds/gerar_seeds.py). Só aceita se o modelo concordar com a
        história (vermelho em outubro, subindo, fator financeiro entre os 2 principais) e
        fica com a maior subida no semestre."""
        if self._modelo is None:
            return None
        from app.risk.atributos import TODAS
        from app.risk.recomendacao import recomendar

        textuais = {"forma_ingresso", "grau_academico", "turno", "estado_civil", "sexo"}
        melhor: tuple[float, str, str, list[Any]] | None = None
        for eid in sorted({c["estudante_id"] for c in self.casos.values()} - evitar):
            base = self.features.get(eid)
            n_scores = sum(1 for s in self.scores.values() if s["estudante_id"] == eid)
            if not base or n_scores < 6:
                continue
            f0 = {
                k: (float(v) if isinstance(v, str) and k not in textuais else v) for k, v in base.items() if k in TODAS
            }
            preds = []
            for i in range(6):
                a = (i / 5) ** 2.5
                f = {
                    **f0,
                    "pct_parcelas_em_aberto": round(0.05 + 0.80 * a, 3),
                    "atraso_medio_dias": round(3 + 117 * a, 1),
                    "pct_parcelas_acordo": 0.0,
                }
                preds.append(self._modelo.predict(f))
            fim, ant = preds[-1], preds[-2]
            topo = sorted((x for x in fim.fatores if x.get("direcao") == "aumenta"), key=lambda x: -x["peso"])[:2]
            no_topo = [x["codigo"] for x in topo if x["codigo"] in codigos]
            if fim.categoria != "vermelho" or fim.probabilidade - ant.probabilidade < 0.05 or not no_topo:
                continue
            subida = fim.probabilidade - preds[0].probabilidade
            if melhor is None or subida > melhor[0]:
                melhor = (subida, eid, no_topo[0], preds)
        if melhor is None:
            return None
        _, eid, fator, preds = melhor
        serie = sorted((s for s in self.scores.values() if s["estudante_id"] == eid), key=lambda s: s["competencia"])
        for sc, pred in zip(serie[-6:], preds, strict=True):
            sc.update(
                probabilidade=pred.probabilidade,
                score_financeiro=pred.score["financeiro"],
                score_academico=pred.score["academico"],
                score_relacionamento=pred.score["relacionamento"],
                categoria=pred.categoria,
                fatores=pred.fatores,
                recomendacao=recomendar(pred.categoria, pred.fatores),
                versao_modelo=pred.versao_modelo,
            )
        caso = next(c for c in self.casos.values() if c["estudante_id"] == eid)
        caso["score_atual_id"] = serie[-1]["id"]
        return eid, fator

    def _simular_uso_chat(self) -> None:
        """Uso agregado do chat nos últimos 30 dias, para o painel. Determinístico (semente fixa).

        As conversas simuladas pertencem a estudantes fictícios sem login, então só
        aparecem nos números agregados do painel, nunca no chat de alguém."""
        rng = random.Random(20261104)  # noqa: S311 - dados simulados, não é segurança
        donos = sorted(e for e, est in self.estudantes.items() if not est.get("perfil_id"))
        temas: list[tuple[list[dict[str, Any]], int]] = []
        for trecho, peso in TEMAS_CHAT:
            cs = [c for c in self.chunks if c["ativo"] and c["titulo_documento"].lower() == trecho]
            if cs:
                temas.append((cs, peso))
        if not donos or not temas:
            return
        pesos = [p for _, p in temas]
        fim = datetime.combine(self.hoje, datetime.min.time(), tzinfo=UTC)
        for dias_atras in range(30, 0, -1):
            dia = fim - timedelta(days=dias_atras)
            util = dia.weekday() < 5
            for _ in range(rng.randint(14, 26) if util else rng.randint(3, 8)):
                momento = dia + timedelta(hours=rng.randint(8, 22), minutes=rng.randint(0, 59))
                cid, rid, mid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
                abst = rng.random() < 0.09
                chunks = rng.choices(temas, weights=pesos)[0][0]
                ev = [] if abst else [rng.choice(chunks)]
                self.conversas[cid] = {
                    "id": cid,
                    "estudante_id": rng.choice(donos),
                    "status": "encaminhada_humano" if abst else "aberta",
                    "titulo": "Conversa simulada",
                    "iniciada_em": momento,
                    "atualizado_em": momento,
                    "sintetico": True,
                }
                self.respostas[rid] = {
                    "id": rid,
                    "mensagem_id": mid,
                    "conversa_id": cid,
                    "confianca": round(rng.uniform(0.18, 0.34) if abst else rng.uniform(0.58, 0.93), 3),
                    "abstencao": abst,
                    "latencia_ms": int(rng.lognormvariate(6.2, 0.45)),
                    "versao_modelo": "rag-0.9",
                    "criado_em": momento,
                    "evidencias": [{"chunk_id": c["chunk_id"], "similaridade": 0.7} for c in ev],
                    "sintetico": True,
                }
                if abst:
                    self.encaminhamentos.append(
                        {
                            "id": str(uuid.uuid4()),
                            "conversa_id": cid,
                            "status": "resolvido" if dias_atras > 3 else rng.choice(["aberto", "em_andamento"]),
                            "setor_destino": "ASA",
                            "prazo": momento + timedelta(days=2),
                        }
                    )
                if rng.random() < 0.34:
                    self.feedbacks.append(
                        {
                            "id": str(uuid.uuid4()),
                            "resposta_id": rid,
                            "estudante_id": self.conversas[cid]["estudante_id"],
                            "avaliacao": "util" if rng.random() < (0.45 if abst else 0.84) else "nao_util",
                            "comentario": None,
                            "criado_em": momento,
                        }
                    )

    # ------------------------------------------------------------------ base de conhecimento
    def _sincronizar_chunks(self) -> None:
        """`self.chunks` = todos os trechos com os dados do documento (os inativos ficam
        para o histórico das conversas mostrar a fonte; a busca usa só os ativos)."""
        saida = []
        for c in self.chunks_docs:
            d = self.documentos.get(c["documento_id"])
            if not d:
                continue
            saida.append(
                {
                    "chunk_id": c["chunk_id"],
                    "documento_id": d["id"],
                    "conteudo": c["conteudo"],
                    "titulo_documento": d["titulo"],
                    "fonte_documento": d["fonte"],
                    "data_atualizacao": d["data_atualizacao"],
                    "ativo": bool(c["ativo"] and d["ativo"]),
                }
            )
        self.chunks = saida

    def listar_chunks_ativos(self) -> list[dict[str, Any]]:
        with self._trava:
            return [{k: v for k, v in c.items() if k != "ativo"} for c in self.chunks if c["ativo"]]

    def _gravar_chunks(self, did: str, chunks: list[dict[str, Any]]) -> None:
        for c in self.chunks_docs:
            if c["documento_id"] == did:
                c["ativo"] = False
        for i, c in enumerate(chunks):
            self.chunks_docs.append(
                {
                    "chunk_id": str(uuid.uuid4()),
                    "documento_id": did,
                    "ordem": i,
                    "conteudo": c["conteudo"],
                    "embedding": c.get("embedding"),
                    "ativo": True,
                }
            )

    def listar_documentos(
        self, busca: str | None, categoria: str | None, ativo: bool | None, pagina: int, por_pagina: int
    ) -> tuple[list[dict[str, Any]], int]:
        from app.rag.texto import normalizar

        ds = [
            self._resumo_doc(d)
            for d in sorted(self.documentos.values(), key=lambda d: d["data_atualizacao"], reverse=True)
            if (ativo is None or d["ativo"] == ativo)
            and (not categoria or d["categoria"] == categoria)
            and (not busca or normalizar(busca) in normalizar(d["titulo"]))
        ]
        return ds[(pagina - 1) * por_pagina : pagina * por_pagina], len(ds)

    def criar_documento(self, d: dict[str, Any]) -> str:
        with self._trava:
            did = super().criar_documento(d)
            self.documentos[did]["data_atualizacao"] = _dt(self.documentos[did]["data_atualizacao"])
            self._sincronizar_chunks()
            return did

    def nova_versao_documento(self, d: dict[str, Any]) -> None:
        with self._trava:
            super().nova_versao_documento(d)
            doc = self.documentos[d["documento_id"]]
            doc["data_atualizacao"] = _dt(doc["data_atualizacao"])
            self._sincronizar_chunks()

    def desativar_documento(self, documento_id: str, motivo: str, usuario_id: str) -> None:
        with self._trava:
            super().desativar_documento(documento_id, motivo, usuario_id)
            self._sincronizar_chunks()

    # ------------------------------------------------------------------ fila
    def _linha_fila(self, estudante_id: str) -> dict[str, Any] | None:
        linha = super()._linha_fila(estudante_id)
        if linha:
            e = self.estudantes[estudante_id]
            linha["faixa_distancia"] = e.get("faixa_distancia")
            linha["regiao"] = e.get("regiao")
        return linha

    # ------------------------------------------------------------------ painel
    def dashboard(self, de: date, ate: date) -> dict[str, Any]:
        def no_periodo(t: datetime | None) -> bool:
            return t is not None and de <= t.date() <= ate

        resp = [r for r in self.respostas.values() if no_periodo(r.get("criado_em"))]
        ids = {r["id"] for r in resp}
        conv = {r["conversa_id"] for r in resp}
        abst = sum(1 for r in resp if r["abstencao"])
        fbs = [f for f in self.feedbacks if f["resposta_id"] in ids]
        lat = sorted(r["latencia_ms"] for r in resp if r.get("latencia_ms"))

        por_dia: dict[date, list[int]] = {}
        for r in resp:
            dia = por_dia.setdefault(r["criado_em"].date(), [0, 0])
            dia[0] += 1
            dia[1] += int(r["abstencao"])
        citacoes: Counter[str] = Counter()
        doc_do_chunk = {c["chunk_id"]: c["documento_id"] for c in self.chunks}
        for r in resp:
            for did in {doc_do_chunk.get(e["chunk_id"]) for e in r["evidencias"]} - {None}:
                citacoes[did] += 1

        dist = dict.fromkeys(("verde", "amarelo", "vermelho"), 0)
        for e in self.estudantes:
            if linha := self._linha_fila(e):
                dist[linha["categoria"]] += 1
        mensal: dict[date, dict[str, int]] = {}
        for sc in self.scores.values():
            m = mensal.setdefault(sc["competencia"], dict.fromkeys(("verde", "amarelo", "vermelho"), 0))
            m[sc["categoria"]] += 1

        vals = [v for v in self.validacoes if no_periodo(v["criado_em"])]
        criado = {c["id"]: c.get("criado_em") for c in self.casos.values()}
        horas = [
            (v["criado_em"] - criado[v["caso_id"]]).total_seconds() / 3600
            for v in vals
            if criado.get(v["caso_id"]) and v["criado_em"] >= criado[v["caso_id"]]
        ]
        enc = Counter(e["status"] for e in self.encaminhamentos)
        versao = next(iter({s["versao_modelo"] for s in self.scores.values()}), "risco-2.0.0")

        return {
            "periodo": {"de": de, "ate": ate},
            "chat": {
                "conversas": len(conv),
                "perguntas": len(resp),
                "estudantes_ativos": len({self.conversas[c]["estudante_id"] for c in conv if c in self.conversas}),
                "taxa_abstencao": round(abst / len(resp), 4) if resp else 0,
                "confianca_media": round(mean(r["confianca"] for r in resp), 4) if resp else None,
                "latencia_p95_ms": lat[int(0.95 * (len(lat) - 1))] if lat else None,
                "latencia_media_ms": int(mean(lat)) if lat else None,
                "feedback": {
                    "util": sum(1 for f in fbs if f["avaliacao"] == "util"),
                    "nao_util": sum(1 for f in fbs if f["avaliacao"] == "nao_util"),
                },
                "perguntas_por_dia": [{"dia": d, "total": t, "abstencoes": a} for d, (t, a) in sorted(por_dia.items())],
                "principais_documentos": [
                    {"documento_id": did, "titulo": self.documentos[did]["titulo"], "citacoes": n}
                    for did, n in citacoes.most_common(5)
                    if did in self.documentos
                ],
            },
            "risco": {
                "distribuicao": dist,
                "distribuicao_mensal": [{"competencia": c, **v} for c, v in sorted(mensal.items())],
                "casos_por_status": dict(Counter(c["status"] for c in self.casos.values())),
                "versao_modelo": versao,
            },
            "validacoes": {
                **{k: sum(1 for v in vals if v["decisao"] == k) for k in ("confirmado", "ajustado", "rejeitado")},
                "tempo_medio_ate_validacao_horas": round(mean(horas), 1) if horas else None,
            },
            "encaminhamentos": {
                "abertos": enc.get("aberto", 0),
                "em_andamento": enc.get("em_andamento", 0),
                "resolvidos": enc.get("resolvido", 0),
            },
            "atualizado_em": _agora(),
        }

    # As escritas do chat e da fila passam pela trava (threadpool do FastAPI)
    def registrar_resposta_chat(self, d: dict[str, Any]) -> dict[str, Any]:
        with self._trava:
            r = super().registrar_resposta_chat(d)
            self.respostas[d["resposta_id"]]["criado_em"] = _agora()
            return r

    def registrar_validacao(self, d: dict[str, Any]) -> dict[str, Any]:
        with self._trava:
            return super().registrar_validacao(d)
