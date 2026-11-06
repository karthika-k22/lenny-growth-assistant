from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.main as main
from backend.database import (
    Base,
    User,
    Conversation,
    ChatMessage,
    GeneratedArtifact,
)

client = TestClient(main.app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200


def test_models_endpoint():
    response = client.get("/api/models")
    assert response.status_code == 200
    assert isinstance(response.json(), (dict, list))


def test_conversations_endpoint():
    response = client.get("/api/conversations")
    assert response.status_code == 200
    assert isinstance(response.json(), (dict, list))


def test_artifacts_endpoint():
    response = client.get("/api/artifacts")
    assert response.status_code == 200
    assert isinstance(response.json(), (dict, list))


def test_delete_conversation_preserves_saved_essays(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    TestSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    monkeypatch.setattr(main, "SessionLocal", TestSessionLocal)

    db = TestSessionLocal()

    try:
        user = User(email="delete-test@example.com")
        db.add(user)
        db.flush()

        conversation = Conversation(
            id="delete-test-conversation",
            user_id=user.id,
            title="Test conversation",
        )
        db.add(conversation)
        db.flush()

        db.add(
            ChatMessage(
                conversation_id=conversation.id,
                role="user",
                content="Test message",
            )
        )

        db.add(
            GeneratedArtifact(
                conversation_id=conversation.id,
                title="Test saved essay",
                content="This essay must survive deletion.",
                artifact_type="markdown",
                provider="groq",
            )
        )

        db.commit()

        main.app.dependency_overrides[
            main.get_current_user
        ] = lambda: user

        response = client.delete(
            "/api/conversations/delete-test-conversation"
        )

        assert response.status_code == 200

        db.expire_all()

        assert (
            db.query(Conversation)
            .filter_by(id="delete-test-conversation")
            .first()
            is None
        )

        assert (
            db.query(ChatMessage)
            .filter_by(
                conversation_id="delete-test-conversation"
            )
            .first()
            is None
        )

        saved_essay = (
            db.query(GeneratedArtifact)
            .filter_by(title="Test saved essay")
            .first()
        )

        assert saved_essay is not None
        assert saved_essay.conversation_id == (
            f"saved-essays-archive-{user.id}"
        )

    finally:
        main.app.dependency_overrides.pop(
            main.get_current_user, None
        )
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_user_data_isolation(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    TestSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    monkeypatch.setattr(main, "SessionLocal", TestSessionLocal)

    db = TestSessionLocal()

    try:
        user_a = User(email="user-a@example.com")
        user_b = User(email="user-b@example.com")
        db.add_all([user_a, user_b])
        db.flush()

        conversation_a = Conversation(
            id="conversation-a",
            user_id=user_a.id,
            title="User A conversation",
        )

        conversation_b = Conversation(
            id="conversation-b",
            user_id=user_b.id,
            title="User B conversation",
        )

        db.add_all([conversation_a, conversation_b])
        db.flush()

        db.add_all([
            ChatMessage(
                conversation_id="conversation-a",
                role="user",
                content="Private message A",
            ),
            ChatMessage(
                conversation_id="conversation-b",
                role="user",
                content="Private message B",
            ),
            GeneratedArtifact(
                conversation_id="conversation-a",
                title="Essay A",
                content="Private essay A",
                artifact_type="markdown",
                provider="groq",
            ),
            GeneratedArtifact(
                conversation_id="conversation-b",
                title="Essay B",
                content="Private essay B",
                artifact_type="markdown",
                provider="groq",
            ),
        ])

        db.commit()

        main.app.dependency_overrides[
            main.get_current_user
        ] = lambda: user_a

        # User A can access their own conversation.
        own = client.get("/api/conversations/conversation-a")
        assert own.status_code == 200

        # User A cannot access User B's conversation.
        other = client.get("/api/conversations/conversation-b")
        assert other.status_code == 404

        # User A cannot delete User B's conversation.
        delete_other = client.delete(
            "/api/conversations/conversation-b"
        )
        assert delete_other.status_code == 404

        # User A cannot see User B's saved essay.
        artifacts = client.get("/api/artifacts")
        assert artifacts.status_code == 200

        artifact_titles = [
            item["title"]
            for item in artifacts.json()["artifacts"]
        ]

        assert "Essay A" in artifact_titles
        assert "Essay B" not in artifact_titles

        # Clearing User A's history must preserve User B's data.
        clear = client.delete("/api/history")
        assert clear.status_code == 200

        db.expire_all()

        assert db.query(Conversation).filter_by(
            id="conversation-a"
        ).first() is None

        assert db.query(Conversation).filter_by(
            id="conversation-b"
        ).first() is not None

        assert db.query(GeneratedArtifact).filter_by(
            title="Essay B"
        ).first() is not None

    finally:
        main.app.dependency_overrides.pop(
            main.get_current_user, None
        )
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_foreign_conversation_rejected_before_groq(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    TestSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    monkeypatch.setattr(main, "SessionLocal", TestSessionLocal)

    db = TestSessionLocal()

    try:
        user_a = User(email="owner@example.com")
        user_b = User(email="intruder@example.com")
        db.add_all([user_a, user_b])
        db.flush()

        db.add(
            Conversation(
                id="private-conversation",
                user_id=user_a.id,
                title="Private conversation",
            )
        )
        db.commit()

        # Authenticate as User B.
        main.app.dependency_overrides[
            main.get_current_user
        ] = lambda: user_b

        # Fail immediately if either endpoint attempts a Groq request.
        def groq_must_not_be_called(*args, **kwargs):
            raise AssertionError(
                "Groq was called before ownership validation."
            )

        monkeypatch.setattr(
            main.httpx,
            "AsyncClient",
            groq_must_not_be_called,
        )

        chat_response = client.post(
            "/api/chat",
            json={
                "message": "Tell me about this conversation.",
                "session_id": "private-conversation",
                "history": [],
                "provider": "groq",
            },
        )

        assert chat_response.status_code == 409
        assert "does not belong" in chat_response.json()["detail"]

        essay_response = client.post(
            "/api/ship-30",
            json={
                "topic": "Product management",
                "session_id": "private-conversation",
                "provider": "groq",
            },
        )

        assert essay_response.status_code == 409
        assert "does not belong" in essay_response.json()["detail"]

    finally:
        main.app.dependency_overrides.pop(
            main.get_current_user, None
        )
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_authenticated_chat_uses_database_history(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    TestSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    monkeypatch.setattr(main, "SessionLocal", TestSessionLocal)
    monkeypatch.setattr(main, "GROQ_API_KEY", "test-key")

    db = TestSessionLocal()

    captured_messages = []

    class MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "Mocked assistant response."
                        }
                    }
                ]
            }

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, headers=None, json=None):
            captured_messages.extend(json["messages"])
            return MockResponse()

    try:
        user = User(email="history-test@example.com")
        db.add(user)
        db.flush()

        conversation = Conversation(
            id="trusted-history-test",
            user_id=user.id,
            title="Trusted history test",
        )
        db.add(conversation)

        db.add(
            ChatMessage(
                conversation_id="trusted-history-test",
                role="user",
                content="This message came from the database.",
            )
        )

        db.commit()

        main.app.dependency_overrides[
            main.get_current_user
        ] = lambda: user

        monkeypatch.setattr(
            main.httpx,
            "AsyncClient",
            MockAsyncClient,
        )

        response = client.post(
            "/api/chat",
            json={
                "message": "What did I say earlier?",
                "session_id": "trusted-history-test",
                "history": [
                    {
                        "role": "user",
                        "content": "FAKE browser history message.",
                    }
                ],
                "provider": "groq",
            },
        )

        assert response.status_code == 200
        assert response.json()["answer"] == (
            "Mocked assistant response."
        )

        sent_content = [
            message["content"]
            for message in captured_messages
        ]

        assert "This message came from the database." in sent_content
        assert "FAKE browser history message." not in sent_content
        assert "What did I say earlier?" in sent_content

    finally:
        main.app.dependency_overrides.pop(
            main.get_current_user, None
        )
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
