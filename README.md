# Async Scraper API

API para scraping assíncrono do Sintegra/GO utilizando filas (RabbitMQ) e cache temporário (Redis). A API envia tarefas de scraping para uma fila; um worker consome as mensagens, realiza o scraping e grava o resultado no Redis.

## Endpoints

- Swagger: `http://localhost:8000/docs`
- `POST /scrape` — body: `{ "cnpj": "00006486000175" }` → retorna `task_id` e `status` inicial `queued`.
- `GET /results/{task_id}` — retorna `status` (`queued|processing|completed|failed`) e, se concluído, o `result`.
- `POST /scrape/batch` — body: `{ "cnpjs": ["00006486000175", "..."] }` → enfileira cada CNPJ e retorna `{cnpj, task_id, status}`.
- `GET /results/batch?task_ids=<id1>&task_ids=<id2>` — consulta resultados de vários `task_id` de uma vez.
- `GET /health` — status do serviço/Redis.

## Como rodar com Docker Compose

1. Crie o arquivo `.env` a partir do exemplo:
   - `cp .env.example .env`
2. Suba o ambiente:
   - `docker compose up --build`
3. Acesse a documentação interativa:
   - `http://localhost:8000/docs`

## Hot reload (Compose Watch)

Para desenvolvimento com atualização automática de código:

- Pré‑requisitos: Docker Desktop/Compose recentes (Compose v2+).
- O projeto já está configurado com `develop.watch` no `docker-compose.yml` para `api` e `worker`.
- A API usa `uvicorn --reload` dentro do container (veja `Dockerfile.api`).

Como usar:

```bash
docker compose watch
```

Observações:

- Se você via a mensagem “watch não está configurado”, isso era porque o `develop.watch` não existia no compose. Agora já está configurado.
- No Windows (Git Bash/PowerShell), rode o comando acima normalmente. Alterações em `app/` e `common/` são sincronizadas para o container da API; alterações em `worker/` e `common/` disparam restart do container do worker.
- Para ambiente sem hot reload, continue usando `docker compose up --build`.

## Estrutura

- `app/`
  - `api/` — rotas, middleware, handlers e schemas
  - `services/` — acesso a RabbitMQ e Redis
  - `main.py` — bootstrap do FastAPI
- `worker/` — consumidor RabbitMQ, scraping e gravação no Redis
- `common/` — configurações, logging e erros compartilhados
- `tests/` — teste unitário do parser

## Desenvolvimento local (sem Docker)

Requisitos: Python 3.11, RabbitMQ e Redis locais.

```bash
# Windows PowerShell (exemplo)
py -3.11 -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# API
uvicorn app.main:app --reload

# Worker
python -m worker.worker
```

## Variáveis de ambiente

- `RABBITMQ_URL` (default `amqp://guest:guest@rabbitmq:5672/`)
- `REDIS_URL` (default `redis://redis:6379/0`)
- `QUEUE_NAME` (default `scrape_tasks`)
- `RESULT_TTL_SECONDS` (default `3600`)
- `REQUEST_TIMEOUT_SECONDS` (default `30`)
- `USER_AGENT` — User-Agent das requisições HTTP

## Log Tracing

Logs estruturados (JSON) com correlação por `task_id`:

```bash
docker compose logs -f api worker | grep <task_id>
```

Eventos esperados: `http_request`, `task_queued`, `rabbitmq_publish`, `worker_started`, `task_started`, `task_completed|task_failed`.


## Persistencia (Postgres)

- Comportamento de persistencia:
  - Controlada via env `PERSIST_TO_DB` (true/false).
  - Sucesso com dados: persiste em Postgres quando `PERSIST_TO_DB=true`.
  - Sucesso sem dados: nao persiste em Postgres (apenas Redis).
  - Falha: nao persiste em Postgres (apenas Redis com status `failed`).
- Tabelas criadas automaticamente quando `PERSIST_TO_DB=true`:
  - `usuario` (persistência normalizada, sem JSON)
    - `cnpj` (string, PK)
    - `inscricao_estadual` (string)
    - `razao_social` (string)
    - `contribuinte` (string)
    - `nome_fantasia` (string)
    - `endereco` (string)
    - `atividade_principal` (string)
    - `unidade_auxiliar` (string)
    - `condicao_uso` (string)
    - `data_final_contrato` (string)
    - `regime_apuracao` (string)
    - `situacao_cadastral` (string)
    - `data_situacao_cadastral` (string)
    - `data_cadastramento` (string)
    - `operacoes_nf_e` (string)
    - `observacoes` (string)
    - `atualizado_em` (string)
    - `data_consulta` (string)
    - `created_at` (datetime)
    - `updated_at` (datetime)

## Orquestracao e Healthcheck

- O `docker-compose.yml` define um healthcheck para o Postgres e faz `api` e `worker` aguardarem o banco ficar pronto antes de iniciar.
- As tabelas sao criadas automaticamente no primeiro start via `common.db.init_db`.

## Endpoints adicionais

- `GET /metrics` — métricas básicas: contagem e latência média por rota.
- Batch:
  - `POST /scrape/batch` — enfileira vários CNPJs.
  - `GET /results/batch` — consulta vários `task_id` de uma vez.

## Exemplos de respostas

- `POST /scrape`
  - 200: `{ "task_id": "<uuid>", "status": "queued" }`

- `GET /results/{task_id}`
  - 200 (completed com dados): `{ "task_id": "<uuid>", "status": "completed", "cnpj": "00006486000175", "has_data": true, "result": { ... } }`
  - 404: `{ "error": { "code": "NOT_FOUND", "message": "Tarefa nao encontrada" } }`

- `POST /scrape/batch`
  - 200: `{ "tasks": [ {"cnpj": "00006486000175", "task_id": "<uuid>", "status": "queued"}, ... ] }`

- `GET /results/batch`
  - 200: `{ "results": [ {"task_id": "...", "status": "...", "cnpj": "...", "has_data": true|false, "result": {..}|null } ], "com_dados": [...], "sem_dados": [...] }`

## Guia rápido de uso da API

- O que faz: enfileira tarefas de scraping por CNPJ (Sintegra/GO), processa via Worker e armazena o resultado no Redis por tempo limitado.
- Como usar (individual):
  - `POST /scrape` com `{ "cnpj": "00006486000175" }` → retorna `task_id`.
  - `GET /results/{task_id}` para acompanhar status e obter `result` quando `completed`.
- Como usar (batch):
  - `POST /scrape/batch` com `{ "cnpjs": ["00006486000175", "00012377000160"] }` → retorna lista com `{cnpj, task_id, status}`.
  - `GET /results/batch?task_ids=<id1>&task_ids=<id2>` para consultar vários de uma vez.

Exemplos (curl)

```bash
# Individual
curl -s -X POST http://localhost:8000/scrape \
  -H 'Content-Type: application/json' \
  -d '{"cnpj":"00006486000175"}'

curl -s http://localhost:8000/results/<task_id>

# Batch
curl -s -X POST http://localhost:8000/scrape/batch \
  -H 'Content-Type: application/json' \
  -d '{"cnpjs":["00006486000175","00012377000160"]}'

curl -s "http://localhost:8000/results/batch?task_ids=<id1>&task_ids=<id2>"
```
