"""Middleware de logging de requisicoes HTTP para a API."""

from __future__ import annotations

import time
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import structlog


logger = structlog.get_logger("api")


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Registra metodo, rota, status e latencia das requisicoes."""

    async def dispatch(self, request: Request, call_next: Callable): 
        """Processa a requisicao/resposta e emite um log estruturado."""
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        try:
            observe_request_metrics(request.url.path, duration_ms)
        except Exception:
            # Validar se eu posso deixar passar sem o log ou se isso da ruim 
            pass
        return response


_METRICS: dict[str, dict[str, float]] = {"__total__": {"count": 0.0, "total_ms": 0.0}}


def observe_request_metrics(path: str, duration_ms: float) -> None:
    bucket = _METRICS.setdefault(path, {"count": 0.0, "total_ms": 0.0})
    bucket["count"] += 1.0
    bucket["total_ms"] += float(duration_ms)
    _METRICS["__total__"]["count"] += 1.0
    _METRICS["__total__"]["total_ms"] += float(duration_ms)


def get_request_metrics() -> dict:
    out: dict[str, dict[str, float | int]] = {}
    for path, data in _METRICS.items():
        count = int(data.get("count", 0))
        total = float(data.get("total_ms", 0.0))
        avg = (total / count) if count else 0.0
        out[path] = {"count": count, "avg_ms": round(avg, 2)}
    return out
