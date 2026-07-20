import os
import sys

import pytest

SRC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, SRC_PATH)


@pytest.fixture(autouse=True)
def _isolate_usage_log(monkeypatch, tmp_path):
    """테스트가 실제 usage_log.md / .usage_state.json에 기록을 남기지 않도록 격리한다."""
    from utils import usage_tracker
    monkeypatch.setattr(usage_tracker, "USAGE_LOG_PATH", str(tmp_path / "usage_log.md"))
    monkeypatch.setattr(usage_tracker, "USAGE_STATE_PATH", str(tmp_path / ".usage_state.json"))
