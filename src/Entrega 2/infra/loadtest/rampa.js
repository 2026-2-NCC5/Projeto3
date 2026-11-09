// =============================================================================
// ASA Turbo · teste de carga em RAMPA (k6): 10 -> 50 -> 100 usuários virtuais
//
// Cenários:
//   usuarios  ramping-vus 10 -> 50 -> 100. Cada VU faz LOGIN uma vez no GoTrue
//             (/auth/v1/token) e depois, conforme o número do VU:
//               ~75% estudantes: POST /api/chat (10 perguntas que se repetem)
//               ~25% atendentes: GET /api/casos (fila) + GET /api/casos/{id}
//   health    5 req/s constantes em /api/health durante todo o teste
//
// O /chat roda no fallback TF-IDF (lexical, em memória): a VM não tem chave de
// embeddings, e assim a carga não bate no Hugging Face/Cloudflare.
//
//   docker run --rm -v "$PWD/infra/loadtest:/t:ro" -v "$PWD/out:/out" \
//     -e BASE_URL=https://54-207-148-68.sslip.io -e DEMO_PASSWORD -e ANON_KEY -e ROTULO=antes \
//     grafana/k6:0.54.0 run /t/rampa.js
// Usuários: infra/loadtest/criar_usuarios_rampa.sh (100 estudantes + 10 atendentes).
// =============================================================================
import http from 'k6/http'
import { check, sleep } from 'k6'
import { Trend, Rate, Counter } from 'k6/metrics'

const BASE = (__ENV.BASE_URL || 'http://localhost:8080').replace(/\/$/, '')
const SENHA = __ENV.DEMO_PASSWORD
const ANON = __ENV.ANON_KEY
const ROTULO = __ENV.ROTULO || 'execucao'
const N_EST = Number(__ENV.N_EST || 100)
const N_ATD = Number(__ENV.N_ATD || 10)
const FATOR = Number(__ENV.FATOR_TEMPO || 1) // 0.2 = ensaio rápido

const latChat = new Trend('lat_chat', true)
const latFila = new Trend('lat_fila', true)
const latCaso = new Trend('lat_caso', true)
const latLogin = new Trend('lat_login', true)
const latHealth = new Trend('lat_health', true)
const abstencoes = new Rate('abstencoes')
const erros5xx = new Rate('erros_5xx')
const limitados = new Counter('respostas_429')

const PERGUNTAS = [
  'Como tiro o atestado de matrícula?',
  'Qual o horário da biblioteca?',
  'Como faço a rematrícula?',
  'Quais bolsas a FECAP oferece?',
  'Como pedir segunda via do boleto?',
  'Como cancelo minha matrícula?',
  'Como faço para trancar a matrícula?',
  'Como funciona a monitoria?',
  'Posso trancar o curso?',
  'Como acesso o portal do aluno?',
]

const d = (s) => `${Math.max(1, Math.round(s * FATOR))}s`
export const options = {
  discardResponseBodies: false,
  scenarios: {
    usuarios: {
      executor: 'ramping-vus', exec: 'usuario', startVUs: 0, gracefulRampDown: '20s',
      stages: [
        { duration: d(30), target: 10 }, { duration: d(90), target: 10 },
        { duration: d(60), target: 50 }, { duration: d(120), target: 50 },
        { duration: d(60), target: 100 }, { duration: d(180), target: 100 },
        { duration: d(30), target: 0 },
      ],
    },
    health: {
      executor: 'constant-arrival-rate', exec: 'health', rate: 5, timeUnit: '1s',
      duration: d(570), preAllocatedVUs: 5, maxVUs: 20,
    },
  },
  thresholds: {
    'http_req_failed{tipo:api}': ['rate<0.02'],
    erros_5xx: ['rate<0.01'],
    lat_chat: ['p(95)<2000'],
    lat_fila: ['p(95)<1500'],
  },
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'max', 'count'],
}

const tokens = {}
function login(email) {
  const r = http.post(`${BASE}/auth/v1/token?grant_type=password`, JSON.stringify({ email, password: SENHA }), {
    headers: { 'Content-Type': 'application/json', apikey: ANON }, tags: { tipo: 'login', name: 'login' },
  })
  latLogin.add(r.timings.duration)
  erros5xx.add(r.status >= 500)
  check(r, { 'login 200': (x) => x.status === 200 })
  return r.status === 200 ? r.json('access_token') : null
}

export function usuario() {
  // VU 1,5,9... = atendente (25%); os demais = estudantes
  const atendente = __VU % 4 === 1
  const email = atendente
    ? `carga.a${String(((__VU - 1) / 4 % N_ATD) + 1 | 0).padStart(2, '0')}@example.com`
    : `carga.e${String(((__VU - 1) % N_EST) + 1).padStart(3, '0')}@example.com`
  if (!tokens[email]) tokens[email] = login(email)
  const t = tokens[email]
  if (!t) { sleep(5); return }
  const h = { headers: { Authorization: `Bearer ${t}`, 'Content-Type': 'application/json' } }

  if (!atendente) {
    const r = http.post(`${BASE}/api/chat`, JSON.stringify({ mensagem: PERGUNTAS[Math.floor(Math.random() * PERGUNTAS.length)] }),
      { ...h, tags: { tipo: 'api', name: 'chat' } })
    latChat.add(r.timings.duration)
    erros5xx.add(r.status >= 500)
    if (r.status === 429) limitados.add(1)
    check(r, { 'chat 200': (x) => x.status === 200 })
    if (r.status === 200) abstencoes.add(r.json('abstencao') === true)
    sleep(3 + Math.random() * 3) // ~13 msgs/min por usuário, abaixo do limite de 20/min
  } else {
    const cat = ['vermelho', 'amarelo', ''][Math.floor(Math.random() * 3)]
    const r = http.get(`${BASE}/api/casos?por_pagina=25${cat ? `&categoria=${cat}` : ''}`, { ...h, tags: { tipo: 'api', name: 'casos' } })
    latFila.add(r.timings.duration)
    erros5xx.add(r.status >= 500)
    check(r, { 'fila 200': (x) => x.status === 200 })
    if (r.status === 200) {
      const itens = r.json('itens') || []
      if (itens.length) {
        const id = itens[Math.floor(Math.random() * itens.length)].estudante.id
        const c = http.get(`${BASE}/api/casos/${id}`, { ...h, tags: { tipo: 'api', name: 'caso' } })
        latCaso.add(c.timings.duration)
        erros5xx.add(c.status >= 500)
        check(c, { 'detalhe 200': (x) => x.status === 200 })
      }
    }
    sleep(2 + Math.random() * 3)
  }
}

export function health() {
  const r = http.get(`${BASE}/api/health`, { tags: { tipo: 'health', name: 'health' } })
  latHealth.add(r.timings.duration)
  erros5xx.add(r.status >= 500)
  check(r, { 'health 200': (x) => x.status === 200 })
}

export function handleSummary(data) {
  return {
    [`/out/k6_${ROTULO}.json`]: JSON.stringify(data, null, 2),
    stdout: textoResumo(data),
  }
}

function textoResumo(data) {
  const m = data.metrics
  const v = (n, k) => (m[n] && m[n].values[k] !== undefined ? m[n].values[k] : NaN)
  const ms = (x) => (isNaN(x) ? '-' : `${x.toFixed(1)} ms`)
  const linhas = [`\n=== k6 · ${ROTULO} · ${BASE} ===`,
    `requisições: ${v('http_reqs', 'count')} (${v('http_reqs', 'rate').toFixed(2)}/s) · falhas: ${(100 * v('http_req_failed', 'rate')).toFixed(2)}% · 5xx: ${(100 * v('erros_5xx', 'rate')).toFixed(2)}%`]
  for (const n of ['lat_health', 'lat_login', 'lat_chat', 'lat_fila', 'lat_caso']) {
    linhas.push(`${n.padEnd(11)} n=${v(n, 'count')}  p50=${ms(v(n, 'med'))}  p95=${ms(v(n, 'p(95)'))}  p99=${ms(v(n, 'p(99)'))}  max=${ms(v(n, 'max'))}`)
  }
  linhas.push(`abstenção: ${(100 * v('abstencoes', 'rate')).toFixed(1)}% · 429: ${v('respostas_429', 'count') || 0}`)
  return linhas.join('\n') + '\n'
}
