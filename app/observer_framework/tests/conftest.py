"""Local `db_session` fixture — identical to tests/conftest.py's, duplicated
here because pytest conftest discovery does not cross from tests/ into
app/**/tests (they're siblings, not a parent/child pair)."""
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql+psycopg://data_core:data_core@localhost:5433/data_core"),
)


@pytest.fixture()
def db_session():
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True, future=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("select 1"))
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL test database is not available: {exc}")

    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(
        bind=connection,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()
