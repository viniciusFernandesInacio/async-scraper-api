"""Esquemas Pydantic usados pela API publica.
- Define os payloads de requisicao e resposta dos endpoints FastAPI.
"""

from pydantic import BaseModel, Field


class ScrapeRequest(BaseModel):
    """Corpo da requisicao para criar tarefa de scraping.
    - Atributos
        - cnpj: str
    """

    cnpj: str = Field(..., description="CNPJ com 14 digitos, somente numeros")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"cnpj": "00006486000175"},
                {"cnpj": "00012377000160"},
                {"cnpj": "00022244000175"},
            ]
        }
    }


class TaskResponse(BaseModel):
    """Modelo de resposta com status/resultado de uma tarefa.
    - Atributos
        - task_id: Identificador unico da tarefa.
        - status: Estado atual (queued, processing, completed, failed).
        - result: Dados extraidos quando concluida.
    """

    task_id: str
    status: str
    result: dict | None = None
    cnpj: str | None = None
    has_data: bool | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"task_id": "d3a6...", "status": "queued"},
                {
                    "task_id": "d3a6...",
                    "status": "completed",
                    "result": {
                        "cnpj": "00.022.244/0001-75",
                        "razao_social": "EMPRESA EXEMPLO LTDA",
                        "situacao_cadastral": "Habilitado",
                    },
                },
            ]
        }
    }


class BatchScrapeRequest(BaseModel):
    """Corpo da requisicao para criar tarefas em lote.
    - Atributos
        - cnpjs: Lista de CNPJs (somente numeros, 14 digitos cada).
    """

    cnpjs: list[str]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"cnpjs": ["00006486000175", "00012377000160", "00022244000175"]}
            ]
        }
    }


class BatchTaskItem(BaseModel):
    """Item de retorno de uma tarefa criada em lote."""

    cnpj: str
    task_id: str
    status: str


class BatchEnqueueResponse(BaseModel):
    """Resposta do enfileiramento em lote."""

    tasks: list[BatchTaskItem]


class BatchResultsResponse(BaseModel):
    """Resposta de consulta de resultados em lote."""

    results: list[TaskResponse]
    com_dados: list[dict]
    sem_dados: list[dict]


class UsuarioResponse(BaseModel):
    """Modelo de resposta para consulta de usuário por CNPJ (tabela `usuario`)."""

    cnpj: str
    inscricao_estadual: str | None = None
    razao_social: str | None = None
    contribuinte: str | None = None
    nome_fantasia: str | None = None
    endereco: str | None = None
    atividade_principal: str | None = None
    unidade_auxiliar: str | None = None
    condicao_uso: str | None = None
    data_final_contrato: str | None = None
    regime_apuracao: str | None = None
    situacao_cadastral: str | None = None
    data_situacao_cadastral: str | None = None
    data_cadastramento: str | None = None
    operacoes_nf_e: str | None = None
    observacoes: str | None = None
    atualizado_em: str | None = None
    data_consulta: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
