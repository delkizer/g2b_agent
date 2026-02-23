import environ
from pathlib import Path


class Config:
    """에이전트 환경 설정"""
    BASE_DIR = Path(__file__).resolve().parent.parent
    ENV_FILE_PATH = BASE_DIR / '.env'

    def __init__(self):
        environ.Env.read_env(env_file=str(self.ENV_FILE_PATH))
        env_default = environ.Env()

        # 환경별 .env 파일 결정
        django_env = env_default('DJANGO_ENV', default='development')
        env_file_name = f".env.{django_env}"
        env_file_path = self.BASE_DIR / env_file_name
        environ.Env.read_env(env_file=str(env_file_path))
        self.env = environ.Env()

    # === 나라장터 API ===
    @property
    def g2b_api_key(self) -> str:
        return self.env('G2B_API_KEY')

    @property
    def g2b_api_base_url(self) -> str:
        return self.env('G2B_API_BASE_URL', default='https://apis.data.go.kr/1230000')

    # === Claude API ===
    @property
    def claude_api_key(self) -> str:
        return self.env('CLAUDE_API_KEY')

    @property
    def claude_model(self) -> str:
        return self.env('CLAUDE_MODEL', default='claude-sonnet-4-20250514')

    @property
    def claude_max_tokens(self) -> int:
        return self.env.int('CLAUDE_MAX_TOKENS', default=2000)

    # === 스케줄 ===
    @property
    def schedule_interval_minutes(self) -> int:
        return self.env.int('SCHEDULE_INTERVAL', default=60)

    # === 내부 API (로컬 FastAPI) ===
    @property
    def internal_api_base_url(self) -> str:
        return self.env('INTERNAL_API_BASE_URL', default='http://127.0.0.1:8100')

    # === EC2 서버 ===
    @property
    def ec2_api_url(self) -> str:
        return self.env('EC2_API_URL', default='http://localhost:8000')

    @property
    def ec2_api_key(self) -> str:
        return self.env('EC2_API_KEY')

    # === Database ===
    @property
    def database_url(self) -> str:
        return self.env('DATABASE_URL', default='postgresql://localhost:5432/spotv')

    # === 키워드 필터 ===
    # 키워드 목록은 Config에서 관리하지 않는다.
    # Phase 1: KeywordFilter 클래스 내 DEFAULT_* 상수 사용
    # Phase 2: agent/config/keywords.json 외부 파일 (KeywordFilter가 직접 로드)
