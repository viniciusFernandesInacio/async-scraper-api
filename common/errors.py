"""Exceções específicas da aplicação para padronizar tratamento de erros."""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class AppError(Exception):
    """Erro base da aplicação.
    - Atributos
        - code: Código curto e estável para identificação do erro.
        - message: Mensagem legível.
        - status_code: Código HTTP sugerido quando aplicável.
        - details: Informações adicionais para diagnóstico.
    """

    code: str
    message: str
    status_code: int = 400
    details: dict | None = None


class BadRequestError(AppError):
    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(code="BAD_REQUEST", message=message, status_code=400, details=details)


class NotFoundError(AppError):
    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(code="NOT_FOUND", message=message, status_code=404, details=details)


class QueuePublishError(AppError):
    def __init__(self, message: str = "Falha ao publicar tarefa", *, details: dict | None = None) -> None:
        super().__init__(code="QUEUE_PUBLISH_FAILED", message=message, status_code=503, details=details)


class ExternalServiceError(AppError):
    def __init__(self, message: str = "Falha em serviço externo", *, details: dict | None = None) -> None:
        super().__init__(code="EXTERNAL_SERVICE_FAILED", message=message, status_code=502, details=details)


class ScrapeError(ExternalServiceError):
    def __init__(self, message: str = "Falha ao consultar página do Sintegra", *, details: dict | None = None) -> None:
        super().__init__(message=message, details=details)

