"""Rotas de scraping: criacao de tarefas e consulta de resultados."""

from __future__ import annotations

import json
import re
import uuid

from fastapi import APIRouter, Request, Query
from app.api.schemas import (
    ScrapeRequest,
    TaskResponse,
    BatchScrapeRequest,
    BatchEnqueueResponse,
    BatchTaskItem,
    BatchResultsResponse,
)
from common.errors import BadRequestError, QueuePublishError, NotFoundError
from app.services.queue import publish_task


router = APIRouter(prefix="", tags=["scraping"])


def _normalize_cnpj(cnpj: str) -> str:
    """Normaliza CNPJ (somente dígitos) e valida dígitos verificadores."""
    digits = re.sub(r"\D", "", cnpj)
    if len(digits) != 14:
        raise BadRequestError("CNPJ deve ter 14 digitos")
    if digits == digits[0] * 14:
        raise BadRequestError("CNPJ invalido")

    def _calc_dv(nums: str, weights: list[int]) -> int:
        s = sum(int(n) * w for n, w in zip(nums, weights))
        r = s % 11
        return 0 if r < 2 else 11 - r

    dv1 = _calc_dv(digits[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    dv2 = _calc_dv(digits[:12] + str(dv1), [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    if digits[-2:] != f"{dv1}{dv2}":
        raise BadRequestError("CNPJ invalido")
    return digits


@router.post(
    "/scrape",
    response_model=TaskResponse,
    response_model_exclude_none=True,
    summary="Cria uma tarefa de scraping para um CNPJ",
    description=(
        "Enfileira uma tarefa no RabbitMQ e registra o status no Redis. "
        "Retorna um task_id para consulta posterior."
    ),
)
async def create_scrape_task(request: Request, payload: ScrapeRequest) -> TaskResponse:
    cnpj = _normalize_cnpj(payload.cnpj)
    task_id = str(uuid.uuid4())
    await request.app.state.cache.set_status(task_id, status="queued", extra={"cnpj": cnpj})
    try:
        await publish_task(task_id, cnpj)
    except QueuePublishError as exc:
        await request.app.state.cache.set_status(task_id, status="failed", result={"error": exc.message})
        raise
    request.app.logger.info("task_queued", task_id=task_id, cnpj=cnpj)  # type: ignore[attr-defined]
    return TaskResponse(task_id=task_id, status="queued")


@router.get(
    "/results/{task_id}",
    response_model=TaskResponse,
    response_model_exclude_none=True,
    summary="Consulta status/resultado da tarefa",
)
async def get_results(request: Request, task_id: str) -> TaskResponse:
    data = await request.app.state.cache.get(task_id)
    if data is None:
        raise NotFoundError("Tarefa nao encontrada")
    result = data.get("result")
    has_data = bool(result)
    cnpj = data.get("cnpj") or (result.get("cnpj") if isinstance(result, dict) else None)
    return TaskResponse(task_id=task_id, status=data.get("status", "unknown"), result=result, cnpj=cnpj, has_data=has_data)


@router.post(
    "/scrape/batch",
    response_model=BatchEnqueueResponse,
    response_model_exclude_none=True,
    summary="Cria tarefas de scraping em lote",
    description="Valida e enfileira cada CNPJ individualmente, retornando seus task_ids.",
)
async def create_scrape_batch(request: Request, payload: BatchScrapeRequest) -> BatchEnqueueResponse:
    tasks: list[BatchTaskItem] = []
    for raw in payload.cnpjs:
        cnpj = _normalize_cnpj(raw)
        task_id = str(uuid.uuid4())
        await request.app.state.cache.set_status(task_id, status="queued", extra={"cnpj": cnpj})
        try:
            await publish_task(task_id, cnpj)
        except QueuePublishError as exc:
            await request.app.state.cache.set_status(task_id, status="failed", result={"error": exc.message})
            tasks.append(BatchTaskItem(cnpj=cnpj, task_id=task_id, status="failed"))
            continue
        tasks.append(BatchTaskItem(cnpj=cnpj, task_id=task_id, status="queued"))
    return BatchEnqueueResponse(tasks=tasks)


@router.get(
    "/results/batch",
    response_model=BatchResultsResponse,
    response_model_exclude_none=True,
    summary="Consulta resultados de varias tarefas",
)
async def get_results_batch(request: Request, task_ids: list[str] = Query(..., description="Lista de task_ids")) -> BatchResultsResponse:
    if not task_ids:
        raise BadRequestError("Forneca ao menos um task_id")
    raw_list = await request.app.state.redis.mget(task_ids)
    results: list[TaskResponse] = []
    com_dados: list[dict] = []
    sem_dados: list[dict] = []
    for tid, raw in zip(task_ids, raw_list):
        if not raw:
            results.append(TaskResponse(task_id=tid, status="unknown", result=None, cnpj=None, has_data=False))
            sem_dados.append({"task_id": tid, "cnpj": None})
            continue
        data = json.loads(raw)
        result = data.get("result")
        has_data = bool(result)
        cnpj = data.get("cnpj") or (result.get("cnpj") if isinstance(result, dict) else None)
        results.append(TaskResponse(task_id=tid, status=data.get("status", "unknown"), result=result, cnpj=cnpj, has_data=has_data))
        (com_dados if has_data else sem_dados).append({"task_id": tid, "cnpj": cnpj})
    return BatchResultsResponse(results=results, com_dados=com_dados, sem_dados=sem_dados)
