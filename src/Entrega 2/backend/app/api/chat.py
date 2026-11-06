"""Rotas do chat. Acesso: SÓ estudante (e só as próprias conversas)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import Chat, Pagina, PorPagina
from app.core.auth import SoEstudante
from app.schemas import ChatPergunta, ChatResposta, ConversaDetalhe, Feedback, FeedbackEntrada, PaginaConversas

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResposta)
def enviar_mensagem(corpo: ChatPergunta, usuario: SoEstudante, chat: Chat) -> ChatResposta:
    return chat.responder(usuario, corpo)


@router.get("/conversas", response_model=PaginaConversas)
def listar_conversas(usuario: SoEstudante, chat: Chat, pagina: Pagina = 1, por_pagina: PorPagina = 25) -> dict:
    return chat.listar(usuario, pagina, por_pagina)


@router.get("/conversas/{conversa_id}", response_model=ConversaDetalhe)
def obter_conversa(conversa_id: UUID, usuario: SoEstudante, chat: Chat) -> dict:
    return chat.detalhe(usuario, str(conversa_id))


@router.post("/feedback", response_model=Feedback, status_code=status.HTTP_201_CREATED)
def enviar_feedback(corpo: FeedbackEntrada, usuario: SoEstudante, chat: Chat) -> dict:
    return chat.feedback(usuario, corpo)
