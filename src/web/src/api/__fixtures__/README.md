# Respostas reais da API (capturadas em 12/10/2026)

Chamadas feitas com `curl` para `POST https://projeto-ia-rho.vercel.app/api/perguntar`.
Os arquivos `.json` são as respostas reais, sem edição (só reformatadas).

| Arquivo | Pergunta enviada | HTTP | Resultado |
|---|---|---|---|
| `abstencao-declaracao-matricula.json` | "Como emitir declaração de matrícula?" | 200 | Abstenção (conf. 0,098); o doc. "Declaração de Matrícula" não aparece nas evidências |
| `abstencao-fora-da-base.json` | "Qual a capital da França?" | 200 | Abstenção (conf. 0,100) |
| `abstencao-texto-identico-ao-chunk.json` | Texto idêntico ao chunk de declaração do `seed_v2.sql` | 200 | Abstenção (conf. 0,021); só 2 evidências, nenhuma correta |
| `erro-debug-pergunta-vazia-http200.json` | `""` | 200 | `[DEBUG] TypeError: type str doesn't define __round__ method` |
| `erro-debug-json-invalido-http500.json` | corpo que não é JSON | 500 | `[DEBUG] Erro no handler: JSONDecodeError...` |

Outras chamadas feitas, sem arquivo salvo (todas HTTP 200 e abstenção):
"Posso trancar minha matrícula?" (0,031), "declaracao matricula" (0,085),
"Quero saber sobre o FIES" (0,039), "Fui reprovado por causa das faltas?" (0,136).
`GET` → HTTP 501 (página HTML). `OPTIONS` → 200 com `Access-Control-Allow-Origin: *`.

## O que foi confirmado
- O formato da resposta bate com o código: `resposta`, `confianca`, `abstencao` e `evidencias[]` com
  `titulo`, `fonte`, `similaridade`, `atualizado_em` e `trecho`.
- `atualizado_em` vem como `"2026-05-10T00:00:00+00:00"` (ISO 8601 com fuso).
- `confianca` no topo **não é arredondada** (ex.: `0.0983730256557465`); nas evidências, `similaridade` vem com 4 casas.
- CORS liberado para qualquer origem.
- Tempo de resposta: 0,5–2,1 s.

## O que NÃO foi possível verificar
- **Nenhuma resposta com `abstencao: false`.** Todas as 9 perguntas, inclusive as 3 sugestões
  da interface atual, terminaram em abstenção. Não existe exemplo real de resposta com sucesso.
- O motivo. Hipótese (não confirmada): os vetores salvos no Supabase e os vetores das perguntas
  foram gerados por métodos diferentes (Hugging Face × fallback TF-IDF), ou os embeddings não
  foram regerados depois do `seed_v2.sql`. Para confirmar, é preciso ver os logs da função no Vercel
  (procurar a linha `[vectorize_hf] falhou`) e se `HF_API_TOKEN` está configurado em Production.
