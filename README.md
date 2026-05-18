# flex-aquadx

Чистый асинхронный Python-микросервис-обёртка над [AquaDX REST v2 API](https://github.com/MewoLab/AquaDX). Даёт удобный, версионированный публичный контракт (`/v1/*`), типизированные DTO, нормализацию данных (achievement → %, inline music meta), кэширование и резолвинг ассетов maimai (jacket, items).

## Возможности (MVP, read-only)

- `GET /v1/players/{username}` — кросс-игровой профиль
- `GET /v1/players/{username}/maimai` — глубокий maimai-профиль
- `GET /v1/players/{username}/maimai/rating` — best35 / best15 с инлайн music meta
- `GET /v1/players/{username}/maimai/recent` — недавние плеи
- `GET /v1/players/{username}/maimai/favorites`, `/trend`, `/scores`
- `GET /v1/maimai/ranking?page=N&size=100`
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

## Особенности upstream API (важно для потребителей)

### `playlog_id` / `track_no` — не путать

В AquaDX `/api/v2/game/mai2/recent` поле `playlogId` — это **в‑сессионный номер трека (1/2/3)**, а не глобальный PK. У одного игрока все 2777 записей могут иметь `playlogId=1`. Глобального PK в JSON-ответе `/recent` нет.

В нашем `/v1/players/{u}/maimai/recent` это поле перемаплено корректно:

| Поле в нашем DTO | Что значит |
|---|---|
| `playlog_id` | всегда `null` — upstream `/recent` глобальный PK не отдаёт |
| `track_no` | 1/2/3 — номер трека внутри кредита (бывший `playlogId` / `trackNo`) |
| `place_name` | имя аркадного аппарата (`placeName`) |
| `user_play_date` | точное локальное время прохождения |
| `play_date` | дата (YYYY‑MM‑DD) |

### Как идентифицировать конкретный заход

Поскольку глобальный PK из `/recent` недоступен, **уникальный составной ключ** — это `(music.id, difficulty, user_play_date)`. Этого достаточно для адресации записи в истории конкретного игрока:

```
GET /v1/players/Sigma/maimai/recent?limit=200
→ ищем запись где music.id = 11663 AND difficulty = "RE:MASTER"
                      AND user_play_date = "2025-05-14 01:19:30"
```

> `/v1/scores/{playlog_id}` намеренно **не реализован** — upstream `/api/v2/game/mai2/playlog?id=X` требует глобальный PK базы данных, который в публичном API через `/recent` не достать. Если когда-нибудь добавим write/admin контекст, где этот PK становится доступен — можно вернуть.

### Wire-формат `user-music-from-list`

Upstream Spring-контроллер: `userMusicFromList(@RP username, @RB musicList: List<Int>)`. Это значит:
- `username` идёт как **request param** (query/form)
- `musicList` — **сырой JSON-массив тела** (`[1,2,3]`), не объект `{"musicList":[...]}`

Наш клиент шлёт правильный формат автоматически — но имейте в виду, если будете писать свой клиент против upstream.

### Поле `achievement` в upstream

Хранится умноженным на `10000` (так `1015234` = `101.5234%`). Наш слой нормализует — клиент получает уже `float` в процентах.

### `best35` / `best15` — 4‑элементный формат

Upstream шлёт `[musicId, level, ratingContribution, achievement]` — четыре элемента, не три. Поле `rating_contribution` в нашем DTO экспонирует вклад трека в общий рейтинг.

### Music meta JSON — отдельный CDN-путь

- Корректный путь: `https://aquadx.net/d/mai2/00/all-music.json` (game code `mai2`, **не** `maimai`)
- Asset URL pattern: `${DATA_HOST}/d/mai2/music/00{pad(id,6).substring(2)}.png`
- Эти пути отличаются от устаревших `dxnet.misakimoe.com` — для свежего инстанса используем `aquadx.net`

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
├── api/                 # роутеры (/v1/players, /v1/maimai/ranking, /v1/players/{u}/maimai/scores, /v1/assets)
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
