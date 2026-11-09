// =============================================================================
// ASA Turbo · ESTRESSE (k6, modelo aberto): acha o ponto de saturação.
// Diferente de rampa.js (usuários com pausa), aqui a taxa de chegada sobe sem
// esperar resposta: quando o servidor satura, a latência explode e aparecem filas.
//   fila  /api/casos + /api/casos/{id} (rota mais cara: 4 consultas ao PostgREST)
//         10 -> 40 -> 80 -> 120 req/s em degraus de 45 s
//   chat  /api/chat a 15 req/s constantes (100 estudantes; abaixo do limite de 20/min)
// Mesmo uso de rodar_rampa.sh:  ROTEIRO=estresse.js infra/loadtest/rodar_rampa.sh estresse_antes
// =============================================================================
import http from 'k6/http'
import { check } from 'k6'
import { Trend, Rate } from 'k6/metrics'

const BASE = (__ENV.BASE_URL || 'http://localhost:8080').replace(/\/$/, '')
const SENHA = __ENV.DEMO_PASSWORD
const ANON = __ENV.ANON_KEY
const ROTULO = __ENV.ROTULO || 'estresse'

const latChat = new Trend('lat_chat', true)
const latFila = new Trend('lat_fila', true)
const latCaso = new Trend('lat_caso', true)
const erros5xx = new Rate('erros_5xx')

const PERGUNTAS = ['Como faço a rematrícula?', 'Como pedir segunda via do boleto?', 'Como funciona a monitoria?',
  'Como faço para trancar a matrícula?', 'Qual o horário da biblioteca?', 'Como acesso o portal do aluno?']

export const options = {
  scenarios: {
    fila: {
      executor: 'ramping-arrival-rate', exec: 'fila', startRate: 10, timeUnit: '1s',
      preAllocatedVUs: 100, maxVUs: 400,
      stages: [
        { duration: '30s', target: 10 }, { duration: '15s', target: 40 }, { duration: '45s', target: 40 },
        { duration: '15s', target: 80 }, { duration: '45s', target: 80 },
        { duration: '15s', target: 120 }, { duration: '45s', target: 120 },
      ],
    },
    chat: {
      executor: 'constant-arrival-rate', exec: 'chat', rate: 15, timeUnit: '1s', duration: '210s',
      preAllocatedVUs: 50, maxVUs: 200,
    },
  },
  summaryTrendStats: ['avg', 'med', 'p(90)', 'p(95)', 'p(99)', 'max', 'count'],
}

export function setup() {
  const login = (email) => http.post(`${BASE}/auth/v1/token?grant_type=password`, JSON.stringify({ email, password: SENHA }),
    { headers: { 'Content-Type': 'application/json', apikey: ANON } }).json('access_token')
  const atendentes = []; const estudantes = []
  for (let i = 1; i <= 10; i++) atendentes.push(login(`carga.a${String(i).padStart(2, '0')}@example.com`))
  for (let i = 1; i <= 100; i++) estudantes.push(login(`carga.e${String(i).padStart(3, '0')}@example.com`))
  return { atendentes, estudantes }
}

let n = 0
export function chat(d) {
  // gira pelos 100 estudantes: 15 req/s = 9 msgs/min por estudante (< 20/min)
  const t = d.estudantes[(n++ * 7 + __VU) % d.estudantes.length]
  const r = http.post(`${BASE}/api/chat`, JSON.stringify({ mensagem: PERGUNTAS[n % PERGUNTAS.length] }),
    { headers: { Authorization: `Bearer ${t}`, 'Content-Type': 'application/json' }, tags: { name: 'chat' }, timeout: '30s' })
  latChat.add(r.timings.duration); erros5xx.add(r.status >= 500 || r.status === 0)
  check(r, { 'chat 200': (x) => x.status === 200 })
}

export function fila(d) {
  const h = { headers: { Authorization: `Bearer ${d.atendentes[__VU % d.atendentes.length]}` }, timeout: '30s' }
  const r = http.get(`${BASE}/api/casos?por_pagina=25`, { ...h, tags: { name: 'casos' } })
  latFila.add(r.timings.duration); erros5xx.add(r.status >= 500 || r.status === 0)
  check(r, { 'fila 200': (x) => x.status === 200 })
  if (r.status === 200) {
    const itens = r.json('itens') || []
    if (itens.length) {
      const c = http.get(`${BASE}/api/casos/${itens[Math.floor(Math.random() * itens.length)].estudante.id}`, { ...h, tags: { name: 'caso' } })
      latCaso.add(c.timings.duration); erros5xx.add(c.status >= 500 || c.status === 0)
    }
  }
}

export function handleSummary(data) {
  const m = data.metrics
  const v = (k, s) => (m[k] && m[k].values[s] !== undefined ? m[k].values[s] : NaN)
  const ms = (x) => (isNaN(x) ? '-' : `${x.toFixed(1)} ms`)
  let txt = `\n=== k6 · ${ROTULO} · ${BASE} ===\nrequisições: ${v('http_reqs', 'count')} (${v('http_reqs', 'rate').toFixed(2)}/s) · falhas: ${(100 * v('http_req_failed', 'rate')).toFixed(2)}% · 5xx/timeout: ${(100 * v('erros_5xx', 'rate')).toFixed(2)}% · iterações descartadas: ${v('dropped_iterations', 'count') || 0}\n`
  for (const k of ['lat_chat', 'lat_fila', 'lat_caso']) txt += `${k.padEnd(9)} n=${v(k, 'count')}  p50=${ms(v(k, 'med'))}  p95=${ms(v(k, 'p(95)'))}  p99=${ms(v(k, 'p(99)'))}  max=${ms(v(k, 'max'))}\n`
  return { [`/out/k6_${ROTULO}.json`]: JSON.stringify(data, null, 2), stdout: txt }
}
