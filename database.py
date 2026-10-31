
import os

from datetime import datetime

from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    DateTime,
    JSON,
    ForeignKey
)

from sqlalchemy.orm import declarative_base, sessionmaker


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./invoice_agent.db"
)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, index=True)

    owner = Column(String, nullable=False, index=True)

    state = Column(String, nullable=False)

    context_id = Column(String, nullable=True)

    input_data = Column(JSON, nullable=True)

    artifacts = Column(JSON, nullable=False, default=list)

    history = Column(JSON, nullable=False, default=list)

    version = Column(Integer, nullable=False, default=1)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )


class ProcessedMessage(Base):
    __tablename__ = "processed_messages"

    principal = Column(String, primary_key=True)

    message_id = Column(String, primary_key=True)

    request_hash = Column(String, nullable=False)

    task_id = Column(
        String,
        ForeignKey("tasks.id"),
        nullable=False
    )

    response_data = Column(JSON, nullable=False)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )


class DecisionCache(Base):
    __tablename__ = "decision_cache"

    package_hash = Column(
        String,
        primary_key=True,
        index=True
    )

    decision_data = Column(
        JSON,
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
