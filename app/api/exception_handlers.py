"""Handlers de excecao para respostas padronizadas em JSON."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import structlog

from common.errors import AppError


logger = structlog.get_logger("api.errors")


def _payload(code: str, message: str, *, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, **({"details": details} if details else {})}}


def register_exception_handlers(app: FastAPI) -> None:
    """Registra handlers para erros comuns retornando JSON padronizado."""

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError):  
        logger.warning("request_validation_error", errors=exc.errors())
        return JSONResponse(status_code=422, content=_payload("VALIDATION_ERROR", "Erro de validacao", details={"errors": exc.errors()}))

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_: Request, exc: StarletteHTTPException):  
        logger.info("http_exception", status_code=exc.status_code, detail=str(exc.detail))
        return JSONResponse(status_code=exc.status_code, content=_payload("HTTP_ERROR", str(exc.detail)))

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError):  
        logger.error("app_error", code=exc.code, message=exc.message, details=exc.details)
        return JSONResponse(status_code=exc.status_code, content=_payload(exc.code, exc.message, details=exc.details))

    @app.exception_handler(Exception)
    async def unhandled_handler(_: Request, exc: Exception): 
        logger.exception("unhandled_exception")
        return JSONResponse(status_code=500, content=_payload("INTERNAL_ERROR", "Erro interno inesperado"))
