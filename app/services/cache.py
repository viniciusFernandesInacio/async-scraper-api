"""Abstração de cache Redis para status e resultados de tarefas."""

import json
from typing import Any
from redis.asyncio import Redis


class Cache:
    """Armazena status e resultados de tarefas em chave-valor.
    - Parâmetros
        - client:Instância assíncrona do cliente Redis.
        - ttl_seconds:Tempo de expiração (segundos) aplicado às entradas de tarefa.
    """

    def __init__(self, client: Redis, ttl_seconds: int) -> None:
        self.client = client
        self.ttl = ttl_seconds

    async def set_status(self, task_id: str, status: str, result: dict | None = None, extra: dict | None = None) -> None:
        """Salva status e, opcionalmente, resultado com TTL e campos extras.
        - Parâmetros
            - task_id: Identificador da tarefa.
            - status: Novo status da tarefa.
            - result: Resultado opcional a ser persistido.
        """
        payload: dict[str, Any] = {"status": status}
        if result is not None:
            payload["result"] = result
        if extra:
            payload.update(extra)
        await self.client.set(task_id, json.dumps(payload), ex=self.ttl)

    async def get(self, task_id: str) -> dict | None:
        """Busca a entrada de uma tarefa no Redis.
        - Retorna o objeto JSON decodificado ou ``None`` quando ausente.
        """
        raw = await self.client.get(task_id)
        if not raw:
            return None
        return json.loads(raw)
