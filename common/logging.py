"""Configuração compartilhada de logs estruturados.
- Fornece `setup_logging`, que configura o `structlog` para emitir logs em JSON
com timestamp, nível e informações de exceção. É usado pela API e pelo worker
para rastreabilidade consistente e legível por máquinas.
"""

from __future__ import annotations
import logging
import sys
import structlog


def setup_logging(level: int = logging.INFO) -> None:
    """Configura o `structlog` e o logging padrão.
    - Parâmetros
        - level: Nível mínimo de log para o logger e handlers raiz.
    """
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
