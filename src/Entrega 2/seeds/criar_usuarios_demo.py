#!/usr/bin/env python3
"""
Cria os 3 usuários de demonstração no Supabase Auth e os perfis correspondentes.
==============================================================================
    estudante.demo@example.com   papel estudante
    atendente.demo@example.com   papel atendente
    admin.demo@example.com       papel administrador

Senha: variável DEMO_PASSWORD (veja seeds/README.md). Os UUIDs são fixos e
iguais aos de gerar_seeds.py, para o seed_demo.sql conseguir referenciá-los.

Idempotente: se o usuário já existe, só atualiza senha e perfil.

Uso (da raiz do projeto, com .env preenchido):
    python3 seeds/criar_usuarios_demo.py

Depois rode seeds/seed_demo.sql no SQL Editor do Supabase.
Dependência: requests.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
TIMEOUT = 20

USUARIOS = [
    ("d0000000-0000-4000-8000-000000000001", "estudante.demo@example.com", "estudante", "Júlia Prado (demo)"),
    ("d0000000-0000-4000-8000-000000000002", "atendente.demo@example.com", "atendente", "Marcos Lima (demo)"),
    ("d0000000-0000-4000-8000-000000000003", "admin.demo@example.com", "administrador", "Renata Alves (demo)"),
]


def carregar_env() -> None:
    caminho = RAIZ / ".env"
    if caminho.exists():
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, valor = linha.split("=", 1)
            os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))
    faltando = [v for v in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "DEMO_PASSWORD") if not os.environ.get(v)]
    if faltando:
        sys.exit(f"Faltam variáveis: {', '.join(faltando)}. Preencha {caminho} a partir do .env.example.")


def main() -> None:
    carregar_env()
    url = os.environ["SUPABASE_URL"].rstrip("/")
    chave = os.environ["SUPABASE_SERVICE_KEY"]
    senha = os.environ["DEMO_PASSWORD"]
    cab = {"apikey": chave, "Authorization": f"Bearer {chave}", "Content-Type": "application/json"}

    for uid, email, papel, nome in USUARIOS:
        corpo = {"id": uid, "email": email, "password": senha, "email_confirm": True,
                 "user_metadata": {"nome": nome, "demo": True}}
        r = requests.post(f"{url}/auth/v1/admin/users", headers=cab, json=corpo, timeout=TIMEOUT)
        if r.status_code in (200, 201):
            criado = r.json().get("id")
            if criado != uid:
                sys.exit(f"{email}: o Auth criou o id {criado}, esperado {uid}. "
                         "Apague o usuário no painel e rode de novo.")
            print(f"criado      {email}")
        elif r.status_code == 422 or "already" in r.text.lower():
            r2 = requests.put(f"{url}/auth/v1/admin/users/{uid}", headers=cab,
                              json={"password": senha, "email_confirm": True}, timeout=TIMEOUT)
            if r2.status_code != 200:
                sys.exit(f"{email}: já existe com outro id? HTTP {r2.status_code}: {r2.text[:200]}")
            print(f"atualizado  {email}")
        else:
            sys.exit(f"{email}: HTTP {r.status_code}: {r.text[:200]}")

        perfil = {"id": uid, "papel": papel, "nome_completo": nome, "email": email, "ativo": True}
        r = requests.post(f"{url}/rest/v1/perfis", json=perfil, timeout=TIMEOUT,
                          headers={**cab, "Prefer": "resolution=merge-duplicates,return=minimal"})
        if r.status_code not in (200, 201, 204):
            sys.exit(f"perfil {email}: HTTP {r.status_code}: {r.text[:200]}")
        print(f"perfil ok   {email} ({papel})")

    print("\nPronto. Agora rode seeds/seed_demo.sql no SQL Editor do Supabase.")


if __name__ == "__main__":
    main()
