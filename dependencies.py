from sqlmodel import Session
from database import engine

def get_session():
    """Dependency for FastAPI to manage database sessions."""
    with Session(engine) as session:
        yield session