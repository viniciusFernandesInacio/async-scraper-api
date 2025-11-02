"""Utilitários de publicação RabbitMQ para enfileirar tarefas de scraping."""

import json

from aio_pika import Message, connect_robust
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from common.config import settings
from common.errors import QueuePublishError


logger = structlog.get_logger("api.queue")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=6), reraise=True)
async def publish_task(task_id: str, cnpj: str) -> None:
    """
    Publica uma nova tarefa de scraping no RabbitMQ.
    - Parâmetros
        - task_id: Identificador único da tarefa.
        - cnpj: CNPJ (14 dígitos) a ser processado pelo worker.
    """
    try:
        connection = await connect_robust(settings.rabbitmq_url)
        try:
            channel = await connection.channel()
            queue = await channel.declare_queue(settings.queue_name, durable=True)
            payload = json.dumps({"task_id": task_id, "cnpj": cnpj}).encode()
            await channel.default_exchange.publish(
                Message(payload, delivery_mode=2), routing_key=queue.name
            )
            logger.info("rabbitmq_publish", task_id=task_id, queue=queue.name)
        finally:
            await connection.close()
    except Exception as exc: 
        logger.error("rabbitmq_publish_failed", task_id=task_id, error=str(exc))
        raise QueuePublishError(details={"queue": settings.queue_name}) from exc

