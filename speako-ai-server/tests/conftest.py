import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

SRC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, SRC_PATH)


@pytest.fixture(autouse=True)
def _isolate_usage_log(monkeypatch, tmp_path):
    """테스트가 실제 usage_log.md / .usage_state.json에 기록을 남기지 않도록 격리한다."""
    from utils import usage_tracker
    monkeypatch.setattr(usage_tracker, "USAGE_LOG_PATH", str(tmp_path / "usage_log.md"))
    monkeypatch.setattr(usage_tracker, "USAGE_STATE_PATH", str(tmp_path / ".usage_state.json"))


@pytest.fixture(autouse=True)
def db_session_factory():
    """
    테스트가 실제 speako-ai-server/data/speako.db를 건드리지 않도록,
    테스트마다 격리된 인메모리 SQLite로 FastAPI의 get_db 의존성을 교체한다.
    autouse라 모든 테스트에 자동 적용되고, DB에 직접 데이터를 심어야 하는 테스트는
    이 픽스처를 인자로 받아 세션 팩토리로 사용하면 된다.
    """
    import main
    from db.database import Base, get_db

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def _override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = _override_get_db
    yield TestSessionLocal
    main.app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
