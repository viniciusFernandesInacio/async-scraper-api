"""Aplicação FastAPI que configura middlewares, dependências e roteadores."""

from __future__ import annotations

from fastapi import FastAPI
from redis.asyncio import from_url as redis_from_url
import structlog

from app.api.exception_handlers import register_exception_handlers
from app.api.middleware import RequestLogMiddleware
from app.api.routes import scraping as scraping_routes
from app.api.routes import system as system_routes
from app.api.routes import users as users_routes
from app.services.cache import Cache
from common.config import settings
from common.db import init_db
from common.logging import setup_logging


setup_logging()
logger = structlog.get_logger("api")

description = (
    "API para scraping assíncrono do Sintegra/GO utilizando RabbitMQ e Redis.\n\n"
    "Fluxo: POST /scrape → task_id → Worker processa → GET /results/{task_id}."
)

openapi_tags = [
    {
        "name": "scraping",
        "description": (
            "Criação e consulta de tarefas de scraping. "
            "Use POST /scrape para um CNPJ ou POST /scrape/batch para vários. "
            "Consulte com GET /results/{task_id} (aceita múltiplos IDs separados por vírgula)."
        ),
    },
    {"name": "system", "description": "Saúde do serviço e métricas básicas."},
    {"name": "users", "description": "Consulta dados persistidos em banco (quando habilitado)."},
]

app = FastAPI(
    title="Async Scraper API",
    version="0.1.0",
    description=description,
    contact={"name": "Async Scraper", "email": "dev@local"},
    license_info={"name": "MIT"},
    openapi_tags=openapi_tags,
)

app.add_middleware(RequestLogMiddleware)


@app.on_event("startup")
async def startup() -> None:
    app.state.redis = redis_from_url(settings.redis_url, decode_responses=False)
    app.state.cache = Cache(app.state.redis, settings.result_ttl_seconds)
    app.logger = logger

    if settings.persist_to_db:
        await __import__("asyncio").to_thread(init_db)
    logger.info("startup_complete", redis_url=settings.redis_url, rabbitmq_url=settings.rabbitmq_url)


@app.on_event("shutdown")
async def shutdown() -> None:
    await app.state.redis.aclose()
    logger.info("shutdown_complete")


app.include_router(scraping_routes.router)
app.include_router(system_routes.router)
app.include_router(users_routes.router)

register_exception_handlers(app)
