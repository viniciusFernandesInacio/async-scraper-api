"""Testes dos endpoints de scraping (single e batch).
- Cobre enfileiramento, normalizacao de CNPJ, falhas de publicacao,
- consultas individuais e em lote (presentes/ausentes).
"""

import json
import pytest
from types import SimpleNamespace
from app.api.routes.scraping import create_scrape_task, get_results, create_scrape_batch, get_results_batch
from app.api.schemas import ScrapeRequest, BatchScrapeRequest


class FakeCache:
    def __init__(self):
        self.store: dict[str, dict] = {}

    async def set_status(self, task_id: str, status: str, result: dict | None = None, extra: dict | None = None):
        payload = {"status": status}
        if result is not None:
            payload["result"] = result
        if extra:
            payload.update(extra)
        self.store[task_id] = payload

    async def get(self, task_id: str):
        return self.store.get(task_id)


class FakeRedis:
    def __init__(self, backing: dict[str, dict]):
        self.backing = backing

    async def mget(self, keys: list[str]):
        out = []
        for k in keys:
            v = self.backing.get(k)
            out.append(json.dumps(v) if v is not None else None)
        return out


async def _noop_publish(task_id: str, cnpj: str) -> None:
    return None


def _req_with_state(cache: FakeCache, redis: FakeRedis):
    logger = SimpleNamespace(info=lambda *a, **k: None)
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(cache=cache, redis=redis), logger=logger))


@pytest.mark.anyio
async def test_create_scrape_task_enqueues(monkeypatch):
    cache = FakeCache()
    redis = FakeRedis(cache.store)
    monkeypatch.setattr("app.api.routes.scraping.publish_task", _noop_publish)
    req = _req_with_state(cache, redis)
    resp = await create_scrape_task(req, ScrapeRequest(cnpj="00006486000175"))
    assert resp.status == "queued"
    assert resp.task_id in cache.store


@pytest.mark.anyio
async def test_get_results_not_found():
    cache = FakeCache()
    redis = FakeRedis(cache.store)
    req = _req_with_state(cache, redis)
    from common.errors import NotFoundError

    with pytest.raises(NotFoundError):
        await get_results(req, "missing-id")


@pytest.mark.anyio
async def test_get_results_returns_payload():
    cache = FakeCache()
    redis = FakeRedis(cache.store)
    req = _req_with_state(cache, redis)
    tid = "t-1"
    await cache.set_status(tid, "completed", result={"cnpj": "00.000.000/0000-00", "razao_social": "X"}, extra={"cnpj": "00000000000000"})
    resp = await get_results(req, tid)
    assert resp.status == "completed"
    assert resp.has_data is True
    assert resp.cnpj == "00000000000000"


@pytest.mark.anyio
async def test_batch_endpoints(monkeypatch):
    cache = FakeCache()
    redis = FakeRedis(cache.store)
    monkeypatch.setattr("app.api.routes.scraping.publish_task", _noop_publish)
    req = _req_with_state(cache, redis)
    payload = BatchScrapeRequest(cnpjs=["00006486000175", "00012377000160"])
    enq = await create_scrape_batch(req, payload)
    assert len(enq.tasks) == 2
    ids = [t.task_id for t in enq.tasks]

    for i, tid in enumerate(ids):
        await cache.set_status(tid, "completed", result={"cnpj": f"00.000.000/000{i}-00"}, extra={"cnpj": f"0000000000000{i}"})
    res = await get_results_batch(req, ids)
    assert len(res.results) == 2
    assert len(res.com_dados) == 2
    assert len(res.sem_dados) == 0


@pytest.mark.anyio
async def test_create_scrape_task_invalid_cnpj_raises(monkeypatch):
    cache = FakeCache()
    redis = FakeRedis(cache.store)
    req = _req_with_state(cache, redis)
    from common.errors import BadRequestError

    with pytest.raises(BadRequestError):
        await create_scrape_task(req, ScrapeRequest(cnpj="123"))


@pytest.mark.anyio
async def test_create_scrape_task_normalizes_cnpj(monkeypatch):
    cache = FakeCache()
    redis = FakeRedis(cache.store)
    monkeypatch.setattr("app.api.routes.scraping.publish_task", _noop_publish)
    req = _req_with_state(cache, redis)

    resp = await create_scrape_task(req, ScrapeRequest(cnpj="00.006.486/0001-75"))
    assert resp.status == "queued"
    stored = cache.store[resp.task_id]
    assert stored["cnpj"].isdigit() and len(stored["cnpj"]) == 14


@pytest.mark.anyio
async def test_create_scrape_task_publish_failure_marks_failed(monkeypatch):
    cache = FakeCache()
    redis = FakeRedis(cache.store)

    from common.errors import QueuePublishError

    async def _fail_publish(task_id: str, cnpj: str):
        raise QueuePublishError("Falha simulada")

    monkeypatch.setattr("app.api.routes.scraping.publish_task", _fail_publish)
    req = _req_with_state(cache, redis)

    with pytest.raises(QueuePublishError):
        await create_scrape_task(req, ScrapeRequest(cnpj="00006486000175"))

    (tid, entry), = cache.store.items()
    assert entry["status"] == "failed"
    assert entry["result"]["error"] == "Falha simulada"


@pytest.mark.anyio
async def test_batch_invalid_cnpj_raises(monkeypatch):
    cache = FakeCache()
    redis = FakeRedis(cache.store)
    req = _req_with_state(cache, redis)
    from common.errors import BadRequestError

    with pytest.raises(BadRequestError):
        await create_scrape_batch(req, BatchScrapeRequest(cnpjs=["00006486000175", "123"]))


@pytest.mark.anyio
async def test_batch_publish_partial_failures(monkeypatch):
    cache = FakeCache()
    redis = FakeRedis(cache.store)

    from common.errors import QueuePublishError

    async def _sometimes_fail(task_id: str, cnpj: str):
        if cnpj.endswith("160"):
            raise QueuePublishError("X")
        return None

    monkeypatch.setattr("app.api.routes.scraping.publish_task", _sometimes_fail)
    req = _req_with_state(cache, redis)
    payload = BatchScrapeRequest(cnpjs=["00006486000175", "00012377000160"]) 
    enq = await create_scrape_batch(req, payload)

    assert len(enq.tasks) == 2
    statuses = {t.cnpj: t.status for t in enq.tasks}
    assert statuses["00006486000175"] == "queued"
    assert statuses["00012377000160"] == "failed"

    failed = [t for t in enq.tasks if t.status == "failed"][0]
    assert cache.store[failed.task_id]["status"] == "failed"


@pytest.mark.anyio
async def test_get_results_batch_mixed_missing_and_present():
    cache = FakeCache()
    redis = FakeRedis(cache.store)
    req = _req_with_state(cache, redis)

    present_id = "ok-1"
    missing_id = "no-1"
    await cache.set_status(present_id, "completed", result={"cnpj": "00.000.000/0001-00"}, extra={"cnpj": "00000000000100"})

    res = await get_results_batch(req, [present_id, missing_id])
    assert len(res.results) == 2
    assert len(res.com_dados) == 1
    assert len(res.sem_dados) == 1
@pytest.fixture
def anyio_backend():
    return "asyncio"
