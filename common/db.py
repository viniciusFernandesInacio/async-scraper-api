"""Camada de persistência com SQLAlchemy/psycopg.
Define o modelo `ScrapeResult` e utilitários para inicialização e gravação de
resultados. Utiliza engine síncrono por simplicidade; chamadas podem ser feitas
de contexto assíncrono com `asyncio.to_thread` quando necessário.
"""

from __future__ import annotations
from datetime import datetime
from typing import Any
from sqlalchemy import create_engine, Column, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, Session
from tenacity import retry, stop_after_attempt, wait_exponential
from common.config import settings


Base = declarative_base()


class ScrapeResult(Base):
    __tablename__ = "scrape_results"

    id = Column(String, primary_key=True)
    cnpj = Column(String, index=True, nullable=False)
    status = Column(String, nullable=False)
    result = Column(JSONB, nullable=True)
    has_data = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Usuario(Base):
    __tablename__ = "usuario"

    cnpj = Column(String, primary_key=True)
    inscricao_estadual = Column(String, nullable=True)
    razao_social = Column(String, nullable=True)
    contribuinte = Column(String, nullable=True)
    nome_fantasia = Column(String, nullable=True)
    endereco = Column(String, nullable=True)
    atividade_principal = Column(String, nullable=True)
    unidade_auxiliar = Column(String, nullable=True)
    condicao_uso = Column(String, nullable=True)
    data_final_contrato = Column(String, nullable=True)
    regime_apuracao = Column(String, nullable=True)
    situacao_cadastral = Column(String, nullable=True)
    data_situacao_cadastral = Column(String, nullable=True)
    data_cadastramento = Column(String, nullable=True)
    operacoes_nf_e = Column(String, nullable=True)
    observacoes = Column(String, nullable=True)
    atualizado_em = Column(String, nullable=True)
    data_consulta = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


def get_engine():
    return create_engine(settings.database_url, pool_pre_ping=True, future=True)


@retry(stop=stop_after_attempt(10), wait=wait_exponential(multiplier=1, min=1, max=5), reraise=True)
def init_db() -> None:
    """Cria tabelas se não existirem."""
    engine = get_engine()
    Base.metadata.create_all(engine)


def upsert_result(task_id: str, cnpj: str, status: str, result: dict | None, has_data: bool) -> None:
    """Insere ou atualiza o resultado de uma tarefa por `task_id`."""
    engine = get_engine()
    with Session(engine) as session:
        existing = session.get(ScrapeResult, task_id)
        if existing:
            existing.cnpj = cnpj
            existing.status = status
            existing.result = result
            existing.has_data = has_data
        else:
            session.add(
                ScrapeResult(
                    id=task_id,
                    cnpj=cnpj,
                    status=status,
                    result=result,
                    has_data=has_data,
                )
            )
        session.commit()


def upsert_usuario(cnpj: str, data: dict[str, Any]) -> None:
    """Insere/atualiza um registro na tabela `usuario` com base no CNPJ.
    - Espera `data` com as chaves mapeadas do scraper (strings).
    """
    engine = get_engine()
    with Session(engine) as session:
        existing = session.get(Usuario, cnpj)
        fields = {
            "inscricao_estadual": data.get("inscricao_estadual"),
            "razao_social": data.get("razao_social"),
            "contribuinte": data.get("contribuinte"),
            "nome_fantasia": data.get("nome_fantasia"),
            "endereco": data.get("endereco"),
            "atividade_principal": data.get("atividade_principal"),
            "unidade_auxiliar": data.get("unidade_auxiliar"),
            "condicao_uso": data.get("condicao_uso"),
            "data_final_contrato": data.get("data_final_contrato"),
            "regime_apuracao": data.get("regime_apuracao"),
            "situacao_cadastral": data.get("situacao_cadastral"),
            "data_situacao_cadastral": data.get("data_situacao_cadastral"),
            "data_cadastramento": data.get("data_cadastramento"),
            "operacoes_nf_e": data.get("operacoes_nf_e"),
            "observacoes": data.get("observacoes"),
            "atualizado_em": data.get("atualizado_em"),
            "data_consulta": data.get("data_consulta"),
        }
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            session.add(Usuario(cnpj=cnpj, **fields))
        session.commit()
