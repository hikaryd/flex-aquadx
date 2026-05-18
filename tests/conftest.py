from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from aquadx.api.deps import reset_cache
from aquadx.main import create_app
from aquadx.meta.loader import reset_loader
from aquadx.settings import reset_settings_cache


@pytest.fixture()
def client() -> Iterator[TestClient]:
    reset_settings_cache()
    reset_cache()
    reset_loader()
    app = create_app()
    with TestClient(app) as c:
        yield c
