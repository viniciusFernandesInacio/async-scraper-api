from __future__ import annotations

"""Worker RabbitMQ que processa tarefas de scraping e grava resultados no Redis."""

import asyncio
import json
from typing import Any

from aio_pika import IncomingMessage, connect_robust
from redis.asyncio import from_url as redis_from_url
import structlog

from common.config import settings
from common.db import init_db, upsert_usuario
from common.logging import setup_logging
from worker.scraper import fetch_cnpj_data_zion as fetch_cnpj_data


setup_logging()
logger = structlog.get_logger("worker")


async def process_message(message: IncomingMessage) -> None:
    """Consome uma mensagem e executa a rotina de scraping."""
    async with message.process():
        payload: dict[str, Any] = json.loads(message.body)
        task_id = payload["task_id"]
        cnpj = payload["cnpj"]
        logger.info("task_started", task_id=task_id, cnpj=cnpj)

        redis = redis_from_url(settings.redis_url, decode_responses=False)
        try:
            from app.services.cache import Cache 

            cache = Cache(redis, settings.result_ttl_seconds)
            await cache.set_status(task_id, "processing")

            result = await asyncio.to_thread(fetch_cnpj_data, cnpj)
            has_data = bool(result)
            await cache.set_status(task_id, "completed", result)

            if has_data and settings.persist_to_db:
                await asyncio.to_thread(upsert_usuario, cnpj, result)
                logger.info("usuario_persisted", task_id=task_id, cnpj=cnpj, fields=len(result or {}))
            else:
                logger.info("usuario_persist_skip", task_id=task_id, cnpj=cnpj, has_data=has_data, persist_to_db=settings.persist_to_db)
            logger.info("task_completed", task_id=task_id)
        except Exception as exc:  
            logger.exception("task_failed", task_id=task_id, cnpj=cnpj, error=str(exc))
            try:
                if 'cache' in locals():
                    await cache.set_status(task_id, "failed", result={"error": str(exc)}, extra={"cnpj": cnpj})
                else:
                    await redis.set(
                        task_id,
                        json.dumps({"status": "failed", "result": {"error": str(exc)}, "cnpj": cnpj}),
                        ex=settings.result_ttl_seconds,
                    )
            except Exception:
                logger.exception("cache_update_failed", task_id=task_id, cnpj=cnpj)
        finally:
            await redis.aclose()


async def main() -> None:
    """Inicia o worker, declara a fila e consome mensagens continuamente."""
    if settings.persist_to_db:
        await asyncio.to_thread(init_db)
    connection = None
    while connection is None:
        try:
            connection = await connect_robust(settings.rabbitmq_url)
        except Exception as exc: 
            logger.warning("rabbitmq_connect_retry", error=str(exc))
            await asyncio.sleep(5)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)
    queue = await channel.declare_queue(settings.queue_name, durable=True)
    logger.info("worker_started", queue=settings.queue_name)
    await queue.consume(process_message)
    try:
        await asyncio.Future()
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
