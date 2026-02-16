import environ
from pathlib import Path


class Config:
    """서버 환경 설정"""
    BASE_DIR = Path(__file__).resolve().parent.parent
    ENV_FILE_PATH = BASE_DIR / '.env'

    def __init__(self):
        # 동일한 2단계 로드 패턴
        environ.Env.read_env(env_file=str(self.ENV_FILE_PATH))
        env_default = environ.Env()

        django_env = env_default('DJANGO_ENV', default='development')
        env_file_path = self.BASE_DIR / f".env.{django_env}"
        environ.Env.read_env(env_file=str(env_file_path))
        self.env = environ.Env()

    # === DB ===
    @property
    def database_url(self) -> str:
        return self.env('DATABASE_URL', default='postgresql://localhost:5432/nara_market')

    # === 인증 ===
    @property
    def internal_api_key(self) -> str:
        return self.env('INTERNAL_API_KEY')

    # === Notion ===
    @property
    def notion_api_key(self) -> str:
        return self.env('NOTION_API_KEY')

    @property
    def notion_database_id(self) -> str:
        return self.env('NOTION_DATABASE_ID')

    @property
    def notion_min_score(self) -> int:
        return self.env.int('NOTION_MIN_SCORE', default=60)
