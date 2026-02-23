"""공통 fixture — Config 환경변수 오버라이드"""

import pytest


@pytest.fixture(autouse=True)
def _override_env(monkeypatch):
    """Config가 참조하는 환경변수를 테스트 값으로 오버라이드한다.

    autouse=True: 모든 테스트에 자동 적용.
    Config.__init__()이 .env 파일을 읽지만,
    monkeypatch로 설정한 값이 우선된다.
    """
    monkeypatch.setenv("DJANGO_ENV", "test")
    monkeypatch.setenv("G2B_API_KEY", "test-api-key")
    monkeypatch.setenv("G2B_API_BASE_URL", "https://test.apis.data.go.kr/1230000")
    monkeypatch.setenv("CLAUDE_API_KEY", "test-claude-key")
    monkeypatch.setenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    monkeypatch.setenv("CLAUDE_MAX_TOKENS", "1000")
    monkeypatch.setenv("SCHEDULE_INTERVAL", "10")
    monkeypatch.setenv("EC2_API_URL", "http://localhost:8000")
    monkeypatch.setenv("EC2_API_KEY", "test-ec2-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost:5432/test_db")
