from __future__ import annotations

from fastapi import FastAPI

from aquadx import __version__
from aquadx.api import health
from aquadx.api.errors import register_exception_handlers
from aquadx.api.v1 import (
    assets as v1_assets,
)
from aquadx.api.v1 import (
    cards as v1_cards,
)
from aquadx.api.v1 import (
    players as v1_players,
)
from aquadx.api.v1 import (
    rankings as v1_rankings,
)
from aquadx.api.v1 import (
    scores as v1_scores,
)
from aquadx.settings import get_settings
from aquadx.utils.logging import configure_logging, install_request_id_middleware


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="aquadx-python",
        version=__version__,
        description=(
            "Clean async microservice wrapping the AquaDX REST v2 API. "
            "Provides player profiles, maimai scores, rating frames, rankings, and asset URLs. "
            "Inherits the CC BY-NC-SA 4.0 licence from upstream — non-commercial only."
        ),
    )
    install_request_id_middleware(app)
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(v1_players.router)
    app.include_router(v1_assets.router)
    app.include_router(v1_rankings.router)
    app.include_router(v1_scores.router)
    app.include_router(v1_cards.router)
    return app


app = create_app()
