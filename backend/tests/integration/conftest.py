import os
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    database_url = os.environ.get(
        "TEST_DATABASE_URL",
        get_settings().database_url,
    )
    engine = create_engine(database_url)
    with Session(engine) as session:
        yield session
