"""Rotas de consulta a usuários persistidos em banco (tabela `usuario`)."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
import re

from fastapi import APIRouter, Request
from sqlalchemy.orm import Session

from app.api.schemas import UsuarioResponse
from common.config import settings
from common.db import Usuario, get_engine
from common.errors import BadRequestError, NotFoundError


router = APIRouter(prefix="", tags=["users"])


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


def _usuario_to_dict(u: Usuario) -> dict[str, Any]:
    def _dt(v: datetime | None) -> str | None:
        return v.isoformat() if v else None

    return {
        "cnpj": u.cnpj,
        "inscricao_estadual": u.inscricao_estadual,
        "razao_social": u.razao_social,
        "contribuinte": u.contribuinte,
        "nome_fantasia": u.nome_fantasia,
        "endereco": u.endereco,
        "atividade_principal": u.atividade_principal,
        "unidade_auxiliar": u.unidade_auxiliar,
        "condicao_uso": u.condicao_uso,
        "data_final_contrato": u.data_final_contrato,
        "regime_apuracao": u.regime_apuracao,
        "situacao_cadastral": u.situacao_cadastral,
        "data_situacao_cadastral": u.data_situacao_cadastral,
        "data_cadastramento": u.data_cadastramento,
        "operacoes_nf_e": u.operacoes_nf_e,
        "observacoes": u.observacoes,
        "atualizado_em": u.atualizado_em,
        "data_consulta": u.data_consulta,
        "created_at": _dt(u.created_at),
        "updated_at": _dt(u.updated_at),
    }


def _fetch_usuario_sync(cnpj_digits: str) -> dict[str, Any] | None:
    engine = get_engine()
    with Session(engine) as session:
        obj = session.get(Usuario, cnpj_digits)
        return _usuario_to_dict(obj) if obj else None


@router.get(
    "/users/{cnpj}",
    response_model=UsuarioResponse,
    response_model_exclude_none=True,
    summary="Consulta usuário por CNPJ no banco",
)
async def get_usuario(request: Request, cnpj: str) -> UsuarioResponse:
    if not settings.persist_to_db:
        raise BadRequestError("Persistencia em banco esta desabilitada (PERSIST_TO_DB=false)")
    cnpj_digits = _normalize_cnpj(cnpj)
    data = await asyncio.to_thread(_fetch_usuario_sync, cnpj_digits)
    if not data:
        raise NotFoundError("Usuario nao encontrado")
    return UsuarioResponse(**data)
