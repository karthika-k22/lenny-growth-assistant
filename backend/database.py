
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import (
    create_engine,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.engine import make_url
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)

# Load environment variables from the project root.
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# SQLite remains the default for local development.
DATABASE_PATH = ROOT / "data" / "lenny_assistant.db"
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

database_url = os.getenv("DATABASE_URL", "").strip()

if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://", "postgresql+pg8000://", 1
        )
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace(
            "postgresql://", "postgresql+pg8000://", 1
        )

    url = make_url(database_url)
    query = dict(url.query)
    query.pop("sslmode", None)
    query.pop("channel_binding", None)
    url = url.set(query=query)

    engine = create_engine(
        url,
        connect_args={"ssl_context": True},
        pool_pre_ping=True,
    )
else:
    engine = create_engine(
        f"sqlite:///{DATABASE_PATH.as_posix()}",
        connect_args={"check_same_thread": False},
    )

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        String(100), primary_key=True
    )
    title: Mapped[str] = mapped_column(
        String(300), default="New conversation"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.id",
    )


class ChatMessage(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(
        String(100), default="unknown"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    conversation: Mapped["Conversation"] = relationship(
        back_populates="messages"
    )


class GeneratedArtifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id"), index=True
    )
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    artifact_type: Mapped[str] = mapped_column(
        String(50), default="markdown"
    )
    provider: Mapped[str] = mapped_column(
        String(100), default="unknown"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


# Create missing tables on the configured database.
Base.metadata.create_all(bind=engine)
