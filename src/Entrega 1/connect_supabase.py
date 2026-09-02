"""
Conexão com o Supabase - ASA Agente para o Estudante
------------------------------------------------------
Antes de rodar, instale a dependência:
    pip install supabase python-dotenv

E crie um arquivo ".env" na mesma pasta deste script com:
    SUPABASE_URL=https://SEU-PROJETO.supabase.co
    SUPABASE_KEY=sua-chave-aqui

Onde encontrar essas informações no painel do Supabase:
    1. Acesse https://supabase.com/dashboard e abra seu projeto
    2. Vá em "Project Settings" (ícone de engrenagem) > "Data API"
       - SUPABASE_URL = campo "Project URL"
    3. Ainda em "Project Settings" > "API Keys"
       - Para testes/leitura simples: use a chave "anon public"
       - Para rodar o seed.sql / inserir dados via script (ignora RLS): use a
         chave "service_role" (NUNCA exponha essa chave no app mobile/frontend,
         ela é só para scripts de backend/administração)
"""

import truststore
truststore.inject_into_ssl()  # usa o repositório de certificados do próprio Windows

import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit(
        "Faltam as variáveis SUPABASE_URL e/ou SUPABASE_KEY.\n"
        "Crie um arquivo .env nesta pasta com essas duas variáveis "
        "(veja instruções no topo deste arquivo)."
    )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def testar_conexao():
    """Testa a conexão listando os documentos oficiais cadastrados."""
    print("\n--- Testando conexão: listando documentos_oficiais ---")
    resposta = supabase.table("documentos_oficiais").select("*").execute()
    for doc in resposta.data:
        print(f"- {doc['titulo']} ({doc['fonte']}) — atualizado em {doc['data_atualizacao']}")
    return resposta.data


def buscar_estudante_por_ra(ra: str):
    """Exemplo de consulta com join simples."""
    print(f"\n--- Buscando estudante com RA {ra} ---")
    resposta = (
        supabase.table("estudantes")
        .select("*, situacao_financeira(*), situacao_academica(*)")
        .eq("ra", ra)
        .execute()
    )
    print(resposta.data)
    return resposta.data


def registrar_conversa(estudante_id: str, canal: str = "chat_portal"):
    """Exemplo de insert: cria uma nova conversa."""
    resposta = (
        supabase.table("conversas")
        .insert({"estudante_id": estudante_id, "canal": canal})
        .execute()
    )
    print("\n--- Conversa criada ---")
    print(resposta.data)
    return resposta.data


def buscar_chunks_similares(embedding: list[float], limite: int = 3, limiar: float = 0.70):
    """
    Chama a função de busca vetorial criada no schema.sql (buscar_chunks_similares).
    O parâmetro 'embedding' precisa ser uma lista de 384 números float
    (gerada por um modelo de embeddings como sentence-transformers/all-MiniLM-L6-v2).
    """
    print("\n--- Buscando chunks mais similares (RAG) ---")
    resposta = supabase.rpc(
        "buscar_chunks_similares",
        {
            "query_embedding": embedding,
            "limite": limite,
            "limiar_similaridade": limiar,
        },
    ).execute()
    print(resposta.data)
    return resposta.data


if __name__ == "__main__":
    testar_conexao()

    # Exemplos de uso (descomente conforme for testando):
    # buscar_estudante_por_ra("20260001")
    # registrar_conversa("uuid-do-estudante-aqui")
    #
    # Para testar a busca vetorial, você precisa primeiro gerar embeddings reais
    # para os chunks (rodando um modelo tipo sentence-transformers) e atualizar
    # a coluna 'embedding' da tabela documentos_chunks. Depois:
    # embedding_da_pergunta = [0.01, 0.02, ...]  # 384 números
    # buscar_chunks_similares(embedding_da_pergunta)
