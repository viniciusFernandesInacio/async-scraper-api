"""Rotas de consulta a usuários persistidos em banco (tabela `usuario`)."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
import re

from fastapi import APIRouter, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import UsuarioResponse, UsuariosBatchResponse
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


def _fetch_usuarios_sync(cnpj_digits: list[str]) -> dict[str, dict[str, Any]]:
    engine = get_engine()
    with Session(engine) as session:
        if not cnpj_digits:
            return {}
        stmt = select(Usuario).where(Usuario.cnpj.in_(cnpj_digits))
        rows = session.execute(stmt).scalars().all()
        return {row.cnpj: _usuario_to_dict(row) for row in rows}


@router.get(
    "/users/{cnpjs:path}",
    response_model=UsuarioResponse | UsuariosBatchResponse,
    response_model_exclude_none=True,
    summary="Consulta usuário(s) por CNPJ no banco",
    description="Envie um ou vários CNPJs separados por vírgula.",
)
async def get_usuario(request: Request, cnpjs: str) -> UsuarioResponse | UsuariosBatchResponse:
    if not settings.persist_to_db:
        raise BadRequestError("Persistencia em banco esta desabilitada (PERSIST_TO_DB=false)")
    raw_values = [value.strip() for value in cnpjs.split(",") if value.strip()]
    if not raw_values:
        raise BadRequestError("Forneca ao menos um CNPJ")

    normalized = []
    for raw in raw_values:
        normalized.append(_normalize_cnpj(raw))

    unique_digits = list(dict.fromkeys(normalized))
    data_map = await asyncio.to_thread(_fetch_usuarios_sync, unique_digits)
    logger = getattr(getattr(request, "app", None), "logger", None)

    if len(raw_values) == 1:
        digits = unique_digits[0]
        data = data_map.get(digits)
        if not data:
            if logger:
                logger.info("user_not_found", cnpj=digits)
            raise NotFoundError("Usuario nao encontrado")
        if logger:
            logger.info("user_found", cnpj=digits)
        return UsuarioResponse(**data)

    encontrados: list[UsuarioResponse] = []
    nao_encontrados: list[str] = []
    for digits in unique_digits:
        data = data_map.get(digits)
        if data:
            encontrados.append(UsuarioResponse(**data))
        else:
            nao_encontrados.append(digits)

    if logger:
        logger.info(
            "users_lookup",
            total=len(unique_digits),
            encontrados=len(encontrados),
            nao_encontrados=nao_encontrados,
        )
    return UsuariosBatchResponse(encontrados=encontrados, nao_encontrados=nao_encontrados)
