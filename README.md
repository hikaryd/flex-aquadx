# flex-aquadx

Чистый асинхронный Python-микросервис-обёртка над [AquaDX REST v2 API](https://github.com/MewoLab/AquaDX). Даёт удобный, версионированный публичный контракт (`/v1/*`), типизированные DTO, нормализацию данных (achievement → %, inline music meta), кэширование и резолвинг ассетов maimai (jacket, items).

## Возможности (MVP, read-only)

- `GET /v1/players/{username}` — кросс-игровой профиль
- `GET /v1/players/{username}/maimai` — глубокий maimai-профиль
- `GET /v1/players/{username}/maimai/rating` — best35 / best15 с инлайн music meta
- `GET /v1/players/{username}/maimai/recent` — недавние плеи
- `GET /v1/players/{username}/maimai/favorites`, `/trend`, `/scores`
- `GET /v1/maimai/ranking?page=N&size=100`
- `GET /v1/scores/{playlogId}`
- `GET /v1/cards/{cardId}`
- `GET /v1/assets/maimai/music/{musicId}/jacket` — 302 / `?proxy=true` / `?format=json`
- `GET /v1/assets/maimai/meta/music`
- `GET /healthz`, `/readyz`, `/v1/info`, `/docs`

## Стек

Python 3.12+ · FastAPI · httpx (async) · pydantic v2 · cachetools · structlog · tenacity · pytest+respx · ruff · mypy --strict · Docker.

## Quickstart

```bash
# native dev
make install
make dev          # http://localhost:8000/docs

# проверки
make verify       # ruff + mypy + pytest --cov-fail-under=80

# через docker compose
make compose-up
```

## Конфигурация (env)

| ENV | Default | Описание |
|---|---|---|
| `AQUADX_BASE_URL` | `https://aquadx.net/aqua` | upstream API |
| `AQUADX_DATA_HOST` | `https://aquadx.net` | CDN ассетов |
| `ASSETS_MODE` | `redirect` | `redirect` или `proxy` |
| `CACHE_BACKEND` | `memory` | `memory` / `redis` / `noop` |
| `HTTP_TIMEOUT_S` | `10` | таймаут upstream |
| `HTTP_RPS` | `5` | rate-limit к upstream |
| `LOG_LEVEL` | `INFO` | уровень логирования |

## Лицензия и условия использования (важно)

Этот проект **наследует лицензию [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) от AquaDX**. Это означает:

- **NonCommercial** — запрещено любое коммерческое использование, включая платный доступ, пожертвования и любую монетизацию.
- **ShareAlike** — производные работы должны распространяться на тех же условиях.
- **Attribution** — обязательно указание авторства AquaDX.

Запуская публичный инстанс этого сервиса вы обязаны соблюдать те же ограничения, что и upstream AquaDX. Подробнее: [docs/self-hosting.md в AquaDX](https://github.com/MewoLab/AquaDX).

## Структура

```
src/aquadx/
├── main.py              # фабрика FastAPI-приложения
├── settings.py          # конфиг из env
├── api/                 # роутеры (/v1/players, /v1/maimai/ranking, /v1/scores, /v1/cards, /v1/assets)
├── clients/             # AquadxClient (httpx + retry + rate-limit)
├── models/              # domain DTO (pydantic v2)
├── mappers/             # нормализация полей и enrichment music meta
├── meta/                # загрузчик music.json (TTL 24h)
├── cache/               # memory / noop (redis — wiring-point)
└── utils/               # logging, ratelimit
tests/                   # unit + integration с respx
```

## Тестирование

```bash
make test                # быстрый pytest
make verify              # ruff + mypy + pytest с coverage gate 80%
```
