#!/usr/bin/env python3
"""
Gerador de dados FICTÍCIOS para demonstração e testes do ASA Turbo.
===================================================================
Tudo aqui é sintético: nomes combinados de listas genéricas, RA falso
(prefixo 99), distribuições escolhidas à mão. Nenhuma linha é derivada de
pessoa real nem estimada a partir da base real do ASA.

Saídas (nesta pasta):
    estudantes_sinteticos.csv  300 linhas, mesmas colunas da base do modelo
                               (base_unificada_asa-final.csv), mês mais recente.
    seed_demo.sql              estudantes, features e scores de 6 meses,
                               casos, validações, contatos e conversas do
                               estudante demo.

Scores: cada estudante recebe uma probabilidade-alvo (≈60% verde, 25% amarelo,
15% vermelho no mês mais recente) e uma trajetória (estável, piorando,
melhorando). As features são geradas a partir de um nível latente de risco, e o
nível é escolhido por busca para que o MODELO REAL (ml/artifacts/risco_v2.joblib)
chegue perto do alvo. Score, categoria, fatores e recomendação vêm do
RiskModel.predict, ou seja, são exatamente o que o backend mostraria.

Determinístico: semente fixa. Rodar duas vezes gera arquivos idênticos
(com o mesmo artefato de modelo).

Uso (precisa das dependências de ml/requirements.txt):
    ml/.venv/bin/python seeds/gerar_seeds.py
"""

from __future__ import annotations

import csv
import json
import math
import random
import sys
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

SEMENTE = 20261106
N_ESTUDANTES = 300
AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent  # src/Entrega 2

COMPETENCIAS = [date(2026, m, 1) for m in range(5, 11)]  # mai..out/2026
LIMIAR_AMARELO = 0.30
LIMIAR_VERMELHO = 0.60

# UUIDs fixos dos usuários de demonstração (criados por criar_usuarios_demo.py)
ID_ESTUDANTE_DEMO = "d0000000-0000-4000-8000-000000000001"
ID_ATENDENTE_DEMO = "d0000000-0000-4000-8000-000000000002"
ID_ADMIN_DEMO = "d0000000-0000-4000-8000-000000000003"

BRT = timezone(timedelta(hours=-3))

PRENOMES = [
    "Ana", "Beatriz", "Bruna", "Camila", "Carolina", "Clara", "Daniela", "Eduarda",
    "Fernanda", "Gabriela", "Helena", "Isabela", "Júlia", "Larissa", "Letícia", "Lívia",
    "Luana", "Mariana", "Natália", "Paula", "Rafaela", "Sofia", "Tainá", "Vitória",
    "André", "Arthur", "Bruno", "Caio", "Daniel", "Diego", "Eduardo", "Felipe",
    "Gabriel", "Gustavo", "Henrique", "Igor", "João", "Leonardo", "Lucas", "Mateus",
    "Murilo", "Otávio", "Pedro", "Rafael", "Renan", "Samuel", "Thiago", "Vinícius",
]
SOBRENOMES = [
    "Almeida", "Alves", "Andrade", "Antunes", "Araújo", "Barbosa", "Barros", "Batista",
    "Cardoso", "Carvalho", "Castro", "Cordeiro", "Correia", "Costa", "Dias", "Duarte",
    "Farias", "Fernandes", "Freitas", "Gomes", "Lima", "Lopes", "Machado", "Martins",
    "Melo", "Mendes", "Monteiro", "Moraes", "Moreira", "Nascimento", "Nogueira", "Nunes",
    "Oliveira", "Pereira", "Pinto", "Prado", "Ramos", "Rezende", "Rocha", "Santana",
    "Santos", "Silva", "Siqueira", "Soares", "Souza", "Teixeira", "Vieira", "Xavier",
]
CURSOS = [
    ("Administração", "Bacharelado", 8), ("Ciências Contábeis", "Bacharelado", 8),
    ("Ciências Econômicas", "Bacharelado", 8), ("Relações Internacionais", "Bacharelado", 8),
    ("Ciência da Computação", "Bacharelado", 8), ("Publicidade e Propaganda", "Bacharelado", 8),
    ("Gestão Financeira", "Tecnólogo", 4), ("Marketing", "Tecnólogo", 4),
]
FORMAS_INGRESSO = [("Vestibular", 45), ("Enem", 30), ("Transferência", 10),
                   ("Segunda Graduação", 5), ("Transferência Mesma Rede", 5), ("Matricula Inicial", 5)]
TURNOS = [("Noite", 55), ("Manhã", 40), ("Integral", 5)]
ESTADOS_CIVIS = [("Solteiro", 80), ("Casado(a)", 12), ("Divorciado(a)", 3), ("Nao informado", 5)]
SEXOS = [("Feminino", 48), ("Masculino", 48), ("Nao informado", 4)]
REGIOES = [("Centro - SP", "ate_5km"), ("Zona Oeste - SP", "5_15km"), ("Zona Sul - SP", "5_15km"),
           ("Zona Norte - SP", "5_15km"), ("Zona Leste - SP", "15_30km"),
           ("Grande SP - ABC", "15_30km"), ("Grande SP - Guarulhos", "15_30km"),
           ("Interior/Litoral - SP", "acima_30km")]

MOTIVOS_SOLICITACAO = [
    "Dúvida sobre segunda via de boleto", "Pedido de declaração de matrícula",
    "Informação sobre bolsas e financiamentos", "Dúvida sobre rematrícula",
    "Orientação sobre aproveitamento de disciplinas", "Acesso ao portal do aluno",
    "Agendamento com coach acadêmico", "Informação sobre estágio",
]
MOTIVOS_CONTATO_ATIVO = [
    "Acompanhamento de frequência", "Convite para plantão de monitoria",
    "Orientação sobre negociação de parcelas", "Apresentação de bolsas disponíveis",
    "Retorno de caso em acompanhamento", "Convite para conversa com coach acadêmico",
]
JUSTIFICATIVAS = {
    "confirmado": [
        "Conversei com a coordenação e a queda de frequência se confirma nas últimas semanas.",
        "Estudante relatou dificuldade com as parcelas; o alerta é coerente com o atendimento.",
        "Notas e assiduidade caíram no bimestre; vou agendar conversa com coach acadêmico.",
    ],
    "ajustado": [
        "Acordo financeiro já foi fechado nesta semana; o risco financeiro deve ser menor.",
        "Faltas foram justificadas por atestado médico entregue na secretaria.",
        "Estudante já está em acompanhamento com a monitoria; ajusto para amarelo.",
    ],
    "rejeitado": [
        "Pendência financeira é de boleto já pago e ainda não baixado no sistema.",
        "Dados de frequência do mês estão incompletos por erro de lançamento do professor.",
    ],
}


def sigmoide(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def limitar(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def sorteio_ponderado(rng: random.Random, opcoes: list[tuple[str, int]]) -> str:
    return rng.choices([o for o, _ in opcoes], weights=[p for _, p in opcoes], k=1)[0]


def novo_uuid(rng: random.Random) -> str:
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))


def categoria(p: float) -> str:
    if p >= LIMIAR_VERMELHO:
        return "vermelho"
    if p >= LIMIAR_AMARELO:
        return "amarelo"
    return "verde"


# ---------------------------------------------------------------------------
# Modelo de estudante sintético
# ---------------------------------------------------------------------------

@dataclass
class Estudante:
    id: str
    ra: str
    nome: str
    curso: str
    grau: str
    duracao: int
    semestre: int
    regiao: str
    faixa: str
    forma_ingresso: str
    turno: str
    estado_civil: str
    sexo: str
    idade: int
    tem_bolsa: bool
    mora_capital: bool
    alvo_final: float         # probabilidade-alvo do mês mais recente
    trajetoria: str           # estavel | piorando | melhorando
    inclinacao: float         # variação mensal do logit-alvo
    mensalidade: float
    ruido: list[list[float]]  # ruído fixo por competência (deixa a busca determinística)
    mensal: list[dict] = field(default_factory=list)


TRAJETORIAS = [("estavel", 50), ("piorando", 25), ("melhorando", 25)]
# Faixas de probabilidade-alvo do mês mais recente (o score final sai do modelo, não daqui)
ALVOS = {"verde": (0.02, 0.26), "amarelo": (0.33, 0.57), "vermelho": (0.64, 0.93)}
DISTRIBUICAO_ALVO = {"verde": 0.60, "amarelo": 0.25, "vermelho": 0.15}
GRADE_Z = [round(-3.0 + 0.1 * i, 2) for i in range(81)]  # nível latente de risco testado na busca


def logit(p: float) -> float:
    p = limitar(p, 1e-4, 1 - 1e-4)
    return math.log(p / (1 - p))


def gerar_estudantes(rng: random.Random) -> list[Estudante]:
    ras = rng.sample(range(99000001, 99099999), N_ESTUDANTES)
    n_verm = round(N_ESTUDANTES * DISTRIBUICAO_ALVO["vermelho"])
    n_amar = round(N_ESTUDANTES * DISTRIBUICAO_ALVO["amarelo"])
    cats = ["vermelho"] * n_verm + ["amarelo"] * n_amar + ["verde"] * (N_ESTUDANTES - n_verm - n_amar)
    rng.shuffle(cats)
    estudantes = []
    for ra, cat in zip(ras, cats):
        curso, grau, duracao = rng.choice(CURSOS)
        regiao, faixa = rng.choice(REGIOES)
        nome = f"{rng.choice(PRENOMES)} {rng.choice(SOBRENOMES)} {rng.choice(SOBRENOMES)}"
        trajetoria = sorteio_ponderado(rng, TRAJETORIAS)
        inclinacao = {"estavel": rng.gauss(0, 0.06), "piorando": rng.uniform(0.25, 0.55),
                      "melhorando": -rng.uniform(0.25, 0.55)}[trajetoria]
        # Evasão se concentra nos primeiros semestres: o alvo vermelho puxa o semestre para o início.
        semestre = {"vermelho": rng.choice([1, 1, 1, 2]), "amarelo": rng.randint(1, min(3, duracao))}.get(
            cat, rng.randint(1, duracao))
        estudantes.append(Estudante(
            id=novo_uuid(rng), ra=str(ra), nome=nome, curso=curso, grau=grau,
            duracao=duracao, semestre=semestre, regiao=regiao, faixa=faixa,
            forma_ingresso=sorteio_ponderado(rng, FORMAS_INGRESSO),
            turno=sorteio_ponderado(rng, TURNOS),
            estado_civil=sorteio_ponderado(rng, ESTADOS_CIVIS),
            sexo=sorteio_ponderado(rng, SEXOS),
            idade=int(limitar(rng.gauss(23, 4.5), 18, 58)),
            tem_bolsa=rng.random() < 0.28,
            mora_capital=faixa in ("ate_5km", "5_15km") or rng.random() < 0.2,
            alvo_final=rng.uniform(*ALVOS[cat]),
            trajetoria=trajetoria,
            inclinacao=inclinacao,
            mensalidade=rng.uniform(900, 2600),
            ruido=[[rng.gauss(0, 1) for _ in range(8)] for _ in COMPETENCIAS],
        ))
    return estudantes


def alvo_do_mes(e: Estudante, t: int) -> float:
    """Probabilidade-alvo da competência t (0..5): o último mês é o alvo; antes, segue a inclinação."""
    return sigmoide(logit(e.alvo_final) + e.inclinacao * (t - (len(COMPETENCIAS) - 1)) + 0.08 * e.ruido[t][7])


def features_de_z(e: Estudante, t: int, z: float, ultimo_contato_ativo: int, total_contatos: int) -> dict:
    """Features no formato da base do modelo para a competência t, dado o nível latente de risco z.

    Monotônicas em z (mesma direção das restrições do modelo): parcelas em aberto, acordo,
    atraso e reprovação sobem com z; nota e frequência caem. O resto é fixo por estudante.
    """
    r = e.ruido[t]
    semestres = max(1, e.semestre - (1 if t < 2 and e.semestre > 1 else 0))
    parcelas = semestres * 6
    pct_aberto = limitar(sigmoide(1.5 * z - 2.6) + 0.015 * r[0], 0, 1)
    pct_acordo = limitar(sigmoide(1.2 * z - 3.2) * 0.6 + 0.01 * r[1], 0, 0.9)
    atraso = -3 + 2.5 * r[2] + max(0.0, z) * 14
    media = limitar(74 - 10 * z + 3 * r[3], 5, 100)
    assid = limitar(90 - 8 * z + 2 * r[4], 5, 100)
    reprov = limitar(sigmoide(1.3 * z - 2.2) * 0.8 + 0.02 * r[5], 0, 1)
    return {
        "tempo_de_curso": float(semestres + (1 if r[7] > 0.8 else 0)),
        "idade": e.idade,
        "mora_sp_capital": e.mora_capital,
        "total_parcelas": parcelas,
        "pct_parcelas_em_aberto": round(pct_aberto, 4),
        "pct_parcelas_acordo": round(pct_acordo, 4),
        "atraso_medio_dias": round(atraso, 2),
        "valor_total_periodo": round(parcelas * e.mensalidade, 2),
        "media_notas": round(media, 2),
        "media_assiduidade": round(assid, 2),
        "pct_reprovacao": round(reprov, 4),
        # piorando -> tendência negativa
        "tendencia_notas": round(-e.inclinacao * 25 + 2 * r[6], 2),
        "tendencia_assiduidade": round(-e.inclinacao * 18 + 1.5 * r[6], 2),
        "total_semestres": semestres,
        # Regra 5: conta SÓ contatos ativos do ASA (o modelo v2 nem usa estes dois campos).
        "total_contatos": total_contatos,
        "dias_desde_ultimo_contato": ultimo_contato_ativo,
        "forma_ingresso": e.forma_ingresso,
        "grau_academico": e.grau,
        "turno": e.turno,
        "estado_civil": e.estado_civil,
        "sexo": e.sexo,
        "tem_bolsa": e.tem_bolsa,
    }


# ---------------------------------------------------------------------------
# Score: modelo real (ml/artifacts/risco_v2.joblib)
# ---------------------------------------------------------------------------

def carregar_modelo():
    sys.path.insert(0, str(RAIZ / "ml"))
    from risco.modelo import RiskModel  # noqa: PLC0415 (só quando o gerador roda)

    return RiskModel.carregar(RAIZ / "ml" / "artifacts" / "risco_v2.joblib")


def features_do_mes_lote(modelo, estudantes: list[Estudante], t: int, contatos: dict[str, list[tuple[int, int]]]) -> dict[str, dict]:
    """Para cada estudante, busca em grade o z cujas features o modelo pontua mais perto do alvo do mês.

    Todos os estudantes do mês vão numa única chamada ao modelo.
    """
    import pandas as pd  # noqa: PLC0415

    candidatos = [features_de_z(e, t, z, *contatos[e.id][t]) for e in estudantes for z in GRADE_Z]
    probs = modelo.probabilidades(pd.DataFrame(candidatos))
    k = len(GRADE_Z)
    out = {}
    for i, e in enumerate(estudantes):
        alvo = alvo_do_mes(e, t)
        bloco = probs[i * k:(i + 1) * k]
        j = min(range(k), key=lambda m: abs(float(bloco[m]) - alvo))
        out[e.id] = candidatos[i * k + j]
    return out


def pontuar(modelo, f: dict) -> dict:
    r = modelo.predict(f)
    return {
        "probabilidade": r["probabilidade"],
        "score_financeiro": r["score"]["financeiro"],
        "score_academico": r["score"]["academico"],
        "score_relacionamento": r["score"]["relacionamento"],
        "categoria": r["categoria"],
        "fatores": r["fatores"],
        "recomendacao": r["recomendacao"],
    }


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

def q(v) -> str:
    """Literal SQL seguro para os tipos usados aqui."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, (date, datetime)):
        return f"'{v.isoformat()}'"
    if isinstance(v, (dict, list)):
        return "'" + json.dumps(v, ensure_ascii=False).replace("'", "''") + "'::jsonb"
    return "'" + str(v).replace("'", "''") + "'"


def insert(tabela: str, colunas: list[str], linhas: list[list], lote: int = 200) -> str:
    partes = []
    for i in range(0, len(linhas), lote):
        valores = ",\n  ".join("(" + ", ".join(q(v) for v in linha) + ")" for linha in linhas[i:i + lote])
        partes.append(f"insert into {tabela} ({', '.join(colunas)}) values\n  {valores};\n")
    return "\n".join(partes)


COLS_FEATURES = [
    "tempo_de_curso", "idade", "mora_sp_capital", "total_parcelas", "pct_parcelas_em_aberto",
    "pct_parcelas_acordo", "atraso_medio_dias", "valor_total_periodo", "media_notas",
    "media_assiduidade", "pct_reprovacao", "tendencia_notas", "tendencia_assiduidade",
    "total_semestres", "total_contatos", "dias_desde_ultimo_contato", "forma_ingresso",
    "grau_academico", "turno", "estado_civil", "sexo", "tem_bolsa",
]

# Cabeçalho idêntico ao de base_unificada_asa-final.csv
CABECALHO_CSV = [
    "ID_ALUNO", "evadiu", "Forma de Ingresso", "Grau Acadêmico", "Turno", "tempo_de_curso",
    "Idade", "Estado Civil", "Sexo", "mora_sp_capital", "total_parcelas",
    "pct_parcelas_em_aberto", "pct_parcelas_acordo", "atraso_medio_dias", "tem_bolsa",
    "valor_total_periodo", "media_notas", "media_assiduidade", "pct_reprovacao",
    "tendencia_notas", "tendencia_assiduidade", "total_semestres", "total_contatos",
    "dias_desde_ultimo_contato",
]


def main() -> None:
    rng = random.Random(SEMENTE)
    modelo = carregar_modelo()
    versao_modelo = modelo.versao
    estudantes = gerar_estudantes(rng)

    # Linhas a inserir
    l_est, l_feat, l_score, l_caso, l_val, l_evt, l_cont, l_csv = [], [], [], [], [], [], [], []

    # Contatos ativos do ASA por competência (dias desde o último, total)
    contatos: dict[str, list[tuple[int, int]]] = {}
    for e in estudantes:
        ultimo_contato, total = rng.randint(10, 240), rng.randint(0, 6)
        contatos[e.id] = []
        for _ in COMPETENCIAS:
            contatos[e.id].append((ultimo_contato, total))
            ultimo_contato = ultimo_contato + 30 if rng.random() > 0.15 else rng.randint(1, 25)
    features = {t: features_do_mes_lote(modelo, estudantes, t, contatos) for t in range(len(COMPETENCIAS))}

    for e in estudantes:
        for t, comp in enumerate(COMPETENCIAS):
            f = features[t][e.id]
            s = pontuar(modelo, f)
            s["id"] = novo_uuid(rng)
            e.mensal.append({"competencia": comp, "features": f, "score": s})
            l_feat.append([novo_uuid(rng), e.id, comp] + [f[c] for c in COLS_FEATURES] + ["seed"])
            calculado = datetime.combine(
                (comp + timedelta(days=32)).replace(day=1), datetime.min.time(), BRT
            ) + timedelta(hours=6)
            l_score.append([s["id"], e.id, comp, s["probabilidade"], s["score_financeiro"],
                            s["score_academico"], s["score_relacionamento"], s["categoria"],
                            s["fatores"], s["recomendacao"], versao_modelo, calculado])

        l_est.append([e.id, None, e.ra, e.nome, e.curso, e.semestre, "regular",
                      e.regiao, e.faixa, e.regiao])

        atual = e.mensal[-1]
        f, s = atual["features"], atual["score"]
        l_csv.append([
            e.ra, "1.0" if rng.random() < s["probabilidade"] else "0.0", f["forma_ingresso"],
            f["grau_academico"], f["turno"], f["tempo_de_curso"], float(f["idade"]),
            f["estado_civil"], f["sexo"], "1.0" if f["mora_sp_capital"] else "0.0",
            float(f["total_parcelas"]), f["pct_parcelas_em_aberto"], f["pct_parcelas_acordo"],
            f["atraso_medio_dias"], "True" if f["tem_bolsa"] else "False",
            f["valor_total_periodo"], f["media_notas"], f["media_assiduidade"],
            f["pct_reprovacao"], f["tendencia_notas"], f["tendencia_assiduidade"],
            float(f["total_semestres"]), float(f["total_contatos"]),
            float(f["dias_desde_ultimo_contato"]),
        ])

        # Contatos e atendimentos (as duas origens)
        for _ in range(rng.choice([0, 0, 1, 1, 1, 2, 2, 3])):
            ativo = rng.random() < 0.4
            quando = datetime(2026, 5, 1, 9, tzinfo=BRT) + timedelta(
                days=rng.randint(0, 180), hours=rng.randint(0, 9))
            l_cont.append([novo_uuid(rng), e.id, ID_ATENDENTE_DEMO if ativo and rng.random() < 0.5 else None,
                           "contato_ativo" if ativo else "solicitacao_estudante",
                           rng.choice(["presencial", "email", "whatsapp", "chat_portal"]),
                           rng.choice(MOTIVOS_CONTATO_ATIVO if ativo else MOTIVOS_SOLICITACAO),
                           None, "Orientação registrada." if rng.random() < 0.7 else None, quando])

        # Caso para quem está amarelo ou vermelho no mês mais recente
        if s["categoria"] != "verde":
            caso_id = novo_uuid(rng)
            if s["categoria"] == "vermelho":
                prioridade = "urgente" if s["probabilidade"] >= 0.75 else "alta"
                prazo = date(2026, 11, 3) + timedelta(days=rng.randint(0, 5))
            else:
                prioridade = "media" if s["probabilidade"] >= 0.45 else "baixa"
                prazo = date(2026, 11, 6) + timedelta(days=rng.randint(0, 14))
            status = rng.choices(["novo", "em_acompanhamento", "contatado"], weights=[60, 25, 15])[0]
            responsavel = ID_ATENDENTE_DEMO if status != "novo" else None
            criado = datetime(2026, 11, 1, 6, tzinfo=BRT)
            categoria_vigente = None
            if status != "novo" and rng.random() < 0.6:
                decisao = rng.choices(["confirmado", "ajustado", "rejeitado"], weights=[60, 28, 12])[0]
                ajustada = None
                if decisao == "ajustado":
                    ajustada = "amarelo" if s["categoria"] == "vermelho" else "verde"
                    categoria_vigente = ajustada
                elif decisao == "rejeitado":
                    categoria_vigente = "verde"
                quando = criado + timedelta(hours=rng.randint(3, 30))
                l_val.append([novo_uuid(rng), caso_id, s["id"], ID_ATENDENTE_DEMO, decisao,
                              rng.choice(JUSTIFICATIVAS[decisao]), ajustada, prioridade, prazo,
                              versao_modelo, quando])
                l_evt.append([novo_uuid(rng), caso_id, ID_ATENDENTE_DEMO, "validacao", None,
                              decisao, None, quando])
            l_caso.append([caso_id, e.id, status, prioridade, prazo, responsavel, s["id"],
                           categoria_vigente, criado])
            l_evt.append([novo_uuid(rng), caso_id, None, "criado", None, "novo",
                          {"origem": "seed", "categoria_modelo": s["categoria"]}, criado])
            if status != "novo":
                l_evt.append([novo_uuid(rng), caso_id, ID_ATENDENTE_DEMO, "status", "novo", status,
                              None, criado + timedelta(hours=2)])

    # ------------------------------------------------------------------ CSV
    with open(AQUI / "estudantes_sinteticos.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(CABECALHO_CSV)
        w.writerows(l_csv)

    # ------------------------------------------------------------------ SQL
    sql = [f"""-- =============================================================================
-- SEED DE DEMONSTRAÇÃO · 100% FICTÍCIO · gerado por seeds/gerar_seeds.py
-- Semente {SEMENTE}. NÃO EDITE À MÃO: altere o gerador e rode de novo.
-- Pré-requisitos: infra/sql/001 e 002 aplicados e seeds/criar_usuarios_demo.py
-- executado (cria os 3 usuários de demo em auth.users e perfis).
-- Pode rodar mais de uma vez: apaga antes o que este seed criou (RA 99xxxxxx).
-- Scores calculados pelo modelo real ({versao_modelo}) sobre features 100% sintéticas.
-- =============================================================================

begin;

do $$ begin
    if (select count(*) from perfis where id in ('{ID_ESTUDANTE_DEMO}', '{ID_ATENDENTE_DEMO}', '{ID_ADMIN_DEMO}')) < 3 then
        raise exception 'Usuários de demo ausentes. Rode antes: python3 seeds/criar_usuarios_demo.py';
    end if;
end $$;

-- Limpa o que um seed anterior criou (cascata: features, scores, casos, contatos, conversas)
delete from feedback_respostas where estudante_id in (select id from estudantes where ra like '99%');
delete from estudantes where ra like '99%';
""",
        "-- Estudantes sintéticos\n",
        insert("estudantes", ["id", "perfil_id", "ra", "nome_exibicao", "curso", "semestre_atual",
                              "status", "endereco_aproximado", "faixa_distancia", "regiao"], l_est),
        "\n-- Features mensais (formato do modelo)\n",
        insert("estudante_features", ["id", "estudante_id", "competencia"] + COLS_FEATURES + ["fonte"], l_feat),
        "\n-- Scores mensais (6 meses)\n",
        insert("scores_risco", ["id", "estudante_id", "competencia", "probabilidade", "score_financeiro",
                                "score_academico", "score_relacionamento", "categoria", "fatores",
                                "recomendacao", "versao_modelo", "calculado_em"], l_score),
        "\n-- Casos (amarelo e vermelho)\n",
        insert("casos_risco", ["id", "estudante_id", "status", "prioridade", "prazo", "atendente_responsavel",
                               "score_atual_id", "categoria_vigente", "criado_em"], l_caso),
        "\n-- Validações humanas de exemplo\n",
        insert("validacoes_caso", ["id", "caso_id", "score_id", "atendente_id", "decisao", "justificativa",
                                   "categoria_ajustada", "prioridade_definida", "prazo_definido",
                                   "versao_modelo", "criado_em"], l_val),
        "\n-- Linha do tempo dos casos\n",
        insert("eventos_caso", ["id", "caso_id", "usuario_id", "tipo", "de", "para", "detalhes", "criado_em"], l_evt),
        "\n-- Contatos e atendimentos\n",
        insert("contatos_asa", ["id", "estudante_id", "atendente_id", "origem", "canal", "motivo",
                                "resumo", "resultado", "ocorrido_em"], l_cont),
        demo_estudante_sql(rng),
        "\ncommit;\n",
    ]
    (AQUI / "seed_demo.sql").write_text("".join(sql), encoding="utf-8")

    cats = [e.mensal[-1]["score"]["categoria"] for e in estudantes]
    for traj in ("estavel", "piorando", "melhorando"):
        grupo = [e for e in estudantes if e.trajetoria == traj]
        delta = sum(e.mensal[-1]["score"]["probabilidade"] - e.mensal[0]["score"]["probabilidade"] for e in grupo) / len(grupo)
        mudou = sum(e.mensal[-1]["score"]["categoria"] != e.mensal[0]["score"]["categoria"] for e in grupo)
        print(f"trajetória {traj}: {len(grupo)} estudantes | variação média do score mai→out {delta:+.3f} "
              f"| {mudou} mudaram de faixa")
    print(f"estudantes: {len(estudantes)} | verde {cats.count('verde')} | amarelo {cats.count('amarelo')} "
          f"| vermelho {cats.count('vermelho')}")
    print(f"features/scores: {len(l_score)} | casos: {len(l_caso)} | validações: {len(l_val)} "
          f"| contatos: {len(l_cont)}")


def demo_estudante_sql(rng: random.Random) -> str:
    """Estudante demo (login) com duas conversas: uma respondida, uma abstenção."""
    c1, c2 = novo_uuid(rng), novo_uuid(rng)
    m1, m2, m3, m4 = (novo_uuid(rng) for _ in range(4))
    r1, r2 = novo_uuid(rng), novo_uuid(rng)
    enc = novo_uuid(rng)
    d1 = datetime(2026, 10, 28, 19, 12, tzinfo=BRT)
    d2 = datetime(2026, 10, 30, 21, 40, tzinfo=BRT)
    # Passos tirados do documento oficial "Atestado de matrícula" (Cesta de Serviços ASA)
    resposta = ("Para emitir o atestado de matrícula:\n1. Acesse o portal.\n"
                "2. Escolha a opção Relatórios.\n3. Emita o documento.")
    abstencao = ("Não encontrei isso nos documentos oficiais. Quer que eu encaminhe para o ASA?")
    return f"""
-- Estudante de demonstração (login: estudante.demo@example.com)
insert into estudantes (id, perfil_id, ra, nome_exibicao, curso, semestre_atual, status, endereco_aproximado, faixa_distancia, regiao)
values ({q(ID_ESTUDANTE_DEMO)}, {q(ID_ESTUDANTE_DEMO)}, '99999901', 'Júlia Prado (demo)', 'Administração', 3, 'regular',
        'Zona Oeste - SP', '5_15km', 'Zona Oeste - SP');

insert into conversas (id, estudante_id, canal, status, titulo, iniciada_em, atualizado_em) values
  ({q(c1)}, {q(ID_ESTUDANTE_DEMO)}, 'chat_portal', 'encerrada', 'Atestado de matrícula', {q(d1)}, {q(d1)}),
  ({q(c2)}, {q(ID_ESTUDANTE_DEMO)}, 'chat_portal', 'encaminhada_humano', 'Animais no campus', {q(d2)}, {q(d2)});

insert into mensagens (id, conversa_id, remetente, conteudo, criado_em) values
  ({q(m1)}, {q(c1)}, 'estudante', 'Como tiro o atestado de matrícula?', {q(d1)}),
  ({q(m2)}, {q(c1)}, 'agente', {q(resposta)}, {q(d1 + timedelta(seconds=3))}),
  ({q(m3)}, {q(c2)}, 'estudante', 'Posso levar meu cachorro para a aula?', {q(d2)}),
  ({q(m4)}, {q(c2)}, 'agente', {q(abstencao)}, {q(d2 + timedelta(seconds=3))});

insert into respostas_agente (id, mensagem_id, resposta_gerada, confianca_score, versao_modelo, abstencao, modelo_embedding, latencia_ms, criado_em) values
  ({q(r1)}, {q(m2)}, {q(resposta)}, 0.7124, 'rag-0.9', false, '@cf/baai/bge-m3', 1840, {q(d1 + timedelta(seconds=3))}),
  ({q(r2)}, {q(m4)}, {q(abstencao)}, 0.4210, 'rag-0.9', true, '@cf/baai/bge-m3', 1530, {q(d2 + timedelta(seconds=3))});

-- Evidência: liga ao chunk real da base de conhecimento, se ela estiver carregada
insert into resposta_evidencias (resposta_id, chunk_id, similaridade, posicao_ranking)
select {q(r1)}, c.id, 0.7124, 1
  from documentos_chunks c join documentos_oficiais d on d.id = c.documento_id
 where d.titulo = 'Atestado de matrícula'
 order by c.ordem limit 1;

insert into feedback_respostas (resposta_id, estudante_id, avaliacao, comentario, criado_em)
values ({q(r1)}, {q(ID_ESTUDANTE_DEMO)}, 'util', null, {q(d1 + timedelta(minutes=1))});

insert into encaminhamentos (id, conversa_id, resposta_id, motivo, setor_destino, prioridade, status, prazo, criado_em)
values ({q(enc)}, {q(c2)}, {q(r2)}, 'Abstenção: pergunta sem resposta na base oficial', 'ASA', 'media', 'aberto',
        {q(d2 + timedelta(days=2))}, {q(d2 + timedelta(seconds=4))});
"""


if __name__ == "__main__":
    main()
