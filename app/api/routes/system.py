"""Rotas de sistema e saude do servico."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.middleware import get_request_metrics


router = APIRouter(prefix="", tags=["system"])


@router.get("/health", summary="Health check")
async def health(request: Request) -> dict:
    """Retorna um payload simples com o estado do Redis."""
    try:
        pong = await request.app.state.redis.ping()
    except Exception:
        pong = False
    return {"status": "ok", "redis": pong}


@router.get("/metrics", summary="Métricas básicas de requisições")
async def metrics() -> dict:
    """Retorna contagem e latência média por rota (memória local)."""
    return {"requests": get_request_metrics()}
