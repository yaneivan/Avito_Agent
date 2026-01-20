import pytest
from sqlmodel import SQLModel, create_engine, Session
from database import engine as real_engine

# Подменяем движок на тестовый (в памяти)
test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

@pytest.fixture(name="session")
def session_fixture():
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        yield session
    SQLModel.metadata.drop_all(test_engine)