"""Configurações da aplicação carregadas de variáveis de ambiente.
- Este módulo define a classe `Settings`, utilizada por todos os serviços para
acessar parâmetros como RabbitMQ, Redis, nomes de fila e opções do cliente HTTP.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Configurações tipadas da aplicação.
    - Os valores são lidos de variáveis de ambiente (pelos aliases definidos) e
    opcionalmente de um arquivo `.env` na raiz do projeto.
    """
    rabbitmq_url: str = Field(
        default="amqp://guest:guest@rabbitmq:5672/", alias="RABBITMQ_URL"
    )
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")
    queue_name: str = Field(default="scrape_tasks", alias="QUEUE_NAME")
    result_ttl_seconds: int = Field(default=3600, alias="RESULT_TTL_SECONDS")
    request_timeout_seconds: int = Field(
        default=30, alias="REQUEST_TIMEOUT_SECONDS"
    )
    user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        alias="USER_AGENT",
    )
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@postgres:5432/scraper",
        alias="DATABASE_URL",
    )
    persist_to_db: bool = Field(default=False, alias="PERSIST_TO_DB")

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


settings = Settings() 
