"""Testes das rotas de usuarios."""

import pytest
from types import SimpleNamespace

from app.api.routes.users import get_usuario
from app.api.schemas import UsuariosBatchResponse
from common.errors import NotFoundError, BadRequestError


def _req_with_logger():
    logger = SimpleNamespace(info=lambda *a, **k: None)
    return SimpleNamespace(app=SimpleNamespace(logger=logger))


@pytest.mark.anyio
async def test_get_usuario_single_found(monkeypatch):
    monkeypatch.setattr("common.config.settings.persist_to_db", True)

    def _fake_fetch(cnpjs: list[str]):
        return {
            "00006486000175": {
                "cnpj": "00006486000175",
                "razao_social": "Empresa Exemplo",
            }
        }

    monkeypatch.setattr("app.api.routes.users._fetch_usuarios_sync", _fake_fetch)
    async def _identity_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)
    monkeypatch.setattr("app.api.routes.users.asyncio.to_thread", _identity_to_thread)

    req = _req_with_logger()
    resp = await get_usuario(req, "00.006.486/0001-75")
    assert resp.cnpj == "00006486000175"
    assert resp.razao_social == "Empresa Exemplo"


@pytest.mark.anyio
async def test_get_usuario_single_not_found(monkeypatch):
    monkeypatch.setattr("common.config.settings.persist_to_db", True)

    def _fake_fetch(cnpjs: list[str]):
        return {}

    monkeypatch.setattr("app.api.routes.users._fetch_usuarios_sync", _fake_fetch)
    async def _identity_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)
    monkeypatch.setattr("app.api.routes.users.asyncio.to_thread", _identity_to_thread)

    req = _req_with_logger()
    with pytest.raises(NotFoundError):
        await get_usuario(req, "00.006.486/0001-75")


@pytest.mark.anyio
async def test_get_usuario_multiple_returns_batch(monkeypatch):
    monkeypatch.setattr("common.config.settings.persist_to_db", True)

    def _fake_fetch(cnpjs: list[str]):
        return {
            "00006486000175": {
                "cnpj": "00006486000175",
                "razao_social": "Empresa Exemplo",
            }
        }

    monkeypatch.setattr("app.api.routes.users._fetch_usuarios_sync", _fake_fetch)
    async def _identity_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)
    monkeypatch.setattr("app.api.routes.users.asyncio.to_thread", _identity_to_thread)

    req = _req_with_logger()
    resp = await get_usuario(req, "00.006.486/0001-75,00.012.377/0001-60")
    assert isinstance(resp, UsuariosBatchResponse)
    assert len(resp.encontrados) == 1
    assert resp.encontrados[0].cnpj == "00006486000175"
    assert resp.nao_encontrados == ["00012377000160"]


@pytest.mark.anyio
async def test_get_usuario_multiple_with_invalid_cnpj(monkeypatch):
    monkeypatch.setattr("common.config.settings.persist_to_db", True)

    async def _identity_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)
    monkeypatch.setattr("app.api.routes.users.asyncio.to_thread", _identity_to_thread)

    req = _req_with_logger()
    with pytest.raises(BadRequestError):
        await get_usuario(req, "00.006.486/0001-75,123")


@pytest.fixture
def anyio_backend():
    return "asyncio"
