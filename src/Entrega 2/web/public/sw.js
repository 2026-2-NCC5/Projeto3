// Service worker do ASA Turbo: cache do "shell" (HTML, JS, CSS, ícones) e página offline.
// Dados da API NUNCA entram no cache (são pessoais e mudam a todo momento).
// Ao publicar uma versão nova, troque VERSAO para descartar o cache antigo.
const VERSAO = 'asa-shell-v1'
const SHELL = ['/', '/offline.html', '/manifest.webmanifest', '/marca.png', '/icones/icone-192.png', '/icones/favicon-32.png']

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(VERSAO).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()))
})

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((chaves) => Promise.all(chaves.filter((k) => k !== VERSAO).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (e) => {
  const req = e.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)
  if (url.origin !== self.location.origin) return // API em outro domínio, Supabase, fontes: rede direto

  // Navegação (abrir/recarregar uma página): rede primeiro; offline, o shell em cache;
  // sem shell, a página offline amigável.
  if (req.mode === 'navigate') {
    e.respondWith(
      fetch(req)
        .then((resp) => {
          if (resp.ok) { const copia = resp.clone(); caches.open(VERSAO).then((c) => c.put('/', copia)) }
          return resp
        })
        .catch(async () => (await caches.match('/')) || caches.match('/offline.html')),
    )
    return
  }

  // Arquivos do build (/assets/*, com hash no nome) e públicos estáticos: cache primeiro.
  const estatico = url.pathname.startsWith('/assets/') || url.pathname.startsWith('/icones/') || /\.(png|svg|webmanifest|woff2?)$/.test(url.pathname)
  if (estatico) {
    e.respondWith(
      caches.match(req).then((emCache) => emCache || fetch(req).then((resp) => {
        if (resp.ok) { const copia = resp.clone(); caches.open(VERSAO).then((c) => c.put(req, copia)) }
        return resp
      })),
    )
  }
  // Todo o resto (inclusive a API na mesma origem): rede, sem cache.
})
