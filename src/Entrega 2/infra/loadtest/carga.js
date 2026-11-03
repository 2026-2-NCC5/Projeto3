// =============================================================================
// Teste de carga do ASA Turbo (k6): 50 usuários simultâneos
//   - 40 estudantes conversando no /chat (perguntas variadas, algumas repetidas)
//   - 10 atendentes navegando na fila (/casos) e abrindo detalhes
// Uso (stack local no ar, usuários de carga criados):
//   docker run --rm --network host -v "$PWD/infra/loadtest:/t" -e DEMO_PASSWORD=... \
//     -e ANON_KEY=... grafana/k6:0.54.0 run /t/carga.js
// =============================================================================
import http from 'k6/http'
import { check, sleep } from 'k6'
import { Trend, Rate } from 'k6/metrics'

const BASE = __ENV.BASE_URL || 'http://localhost:8080'
const SENHA = __ENV.DEMO_PASSWORD
const ANON = __ENV.ANON_KEY

const latChat = new Trend('lat_chat', true)
const latFila = new Trend('lat_fila', true)
const latCaso = new Trend('lat_caso', true)
const abstencoes = new Rate('abstencoes')
const erros = new Rate('erros_5xx')

const PERGUNTAS = [
  'Como tiro o atestado de matrícula?',
  'Qual o horário da biblioteca?',
  'Como faço a rematrícula?',
  'Quais bolsas a FECAP oferece?',
  'Como pedir segunda via do boleto?',
  'Como cancelo minha matrícula?',
  'Onde fica o ASA?',
  'Como funciona a monitoria?',
  'Posso trancar o curso?',
  'Como acesso o portal do aluno?',
]

export const options = {
  scenarios: {
    estudantes: {
      executor: 'ramping-vus', exec: 'estudante', startVUs: 0,
      stages: [{ duration: '30s', target: 40 }, { duration: '2m', target: 40 }, { duration: '15s', target: 0 }],
    },
    atendentes: {
      executor: 'ramping-vus', exec: 'atendente', startVUs: 0,
      stages: [{ duration: '30s', target: 10 }, { duration: '2m', target: 10 }, { duration: '15s', target: 0 }],
    },
  },
  thresholds: {
    'http_req_failed{tipo:api}': ['rate<0.02'],
    lat_chat: ['p(95)<2000'],
    lat_fila: ['p(95)<1500'],
    erros_5xx: ['rate<0.01'],
  },
}

function login(email) {
  const r = http.post(`${BASE}/auth/v1/token?grant_type=password`, JSON.stringify({ email, password: SENHA }), {
    headers: { 'Content-Type': 'application/json', apikey: ANON }, tags: { tipo: 'login' },
  })
  check(r, { 'login 200': (x) => x.status === 200 })
  return r.json('access_token')
}

const tokens = {}
function token(email) {
  if (!tokens[email]) tokens[email] = login(email)
  return tokens[email]
}

export function estudante() {
  const n = String(((__VU - 1) % 50) + 1).padStart(2, '0')
  const h = { headers: { Authorization: `Bearer ${token(`carga.estudante${n}@example.com`)}`, 'Content-Type': 'application/json' }, tags: { tipo: 'api' } }
  const pergunta = PERGUNTAS[Math.floor(Math.random() * PERGUNTAS.length)]
  const r = http.post(`${BASE}/api/chat`, JSON.stringify({ mensagem: pergunta }), h)
  latChat.add(r.timings.duration)
  erros.add(r.status >= 500)
  check(r, { 'chat 200': (x) => x.status === 200, 'tem fontes ou abstenção': (x) => x.status !== 200 || x.json('abstencao') || x.json('fontes').length > 0 })
  if (r.status === 200) abstencoes.add(r.json('abstencao'))
  sleep(4 + Math.random() * 4) // ritmo de quem lê a resposta (abaixo do limite de 20/min)
}

export function atendente() {
  const n = String(((__VU - 1) % 5) + 1).padStart(2, '0')
  const h = { headers: { Authorization: `Bearer ${token(`carga.atendente${n}@example.com`)}` }, tags: { tipo: 'api' } }
  const cat = ['vermelho', 'amarelo', ''][Math.floor(Math.random() * 3)]
  const r = http.get(`${BASE}/api/casos?por_pagina=25${cat ? `&categoria=${cat}` : ''}`, h)
  latFila.add(r.timings.duration)
  erros.add(r.status >= 500)
  check(r, { 'fila 200': (x) => x.status === 200 })
  if (r.status === 200) {
    const itens = r.json('itens')
    if (itens.length) {
      const id = itens[Math.floor(Math.random() * itens.length)].estudante.id
      const d = http.get(`${BASE}/api/casos/${id}`, h)
      latCaso.add(d.timings.duration)
      erros.add(d.status >= 500)
      check(d, { 'detalhe 200': (x) => x.status === 200 })
    }
  }
  sleep(2 + Math.random() * 3)
}
