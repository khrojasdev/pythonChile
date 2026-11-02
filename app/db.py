"""Conexión a la base de datos (SQLite local o PostgreSQL en Render)."""
from pathlib import Path

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from app import config

if config.DATABASE_URL.startswith("sqlite"):
    Path("data").mkdir(exist_ok=True)
    engine = create_engine(config.DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)


def crear_tablas() -> None:
    SQLModel.metadata.create_all(engine)


def sesion() -> Session:
    return Session(engine)


@event.listens_for(Session, "after_commit")
def _invalidar_cache(_session) -> None:
    """Cualquier dato guardado invalida los cálculos en caché."""
    from app import analytics
    analytics.invalidar()
