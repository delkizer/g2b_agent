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

        self._django_env = env_default('DJANGO_ENV', default='development')
        env_file_path = self.BASE_DIR / f".env.{self._django_env}"
        environ.Env.read_env(env_file=str(env_file_path))
        self.env = environ.Env()

    # === 환경 ===
    @property
    def app_env(self) -> str:
        return self._django_env

    # === DB ===
    @property
    def database_url(self) -> str:
        return self.env('DATABASE_URL', default='postgresql://localhost:5432/nara_market')

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        if url.startswith('postgresql://'):
            return url.replace('postgresql://', 'postgresql+asyncpg://', 1)
        return url

    # === 인증 ===
    @property
    def internal_api_key(self) -> str:
        return self.env('INTERNAL_API_KEY')

    # === JWT ===
    @property
    def jwt_key_path(self) -> Path:
        return Path(self.env('JWT_KEY_PATH', default=str(self.BASE_DIR / 'server_env' / 'rsa256')))

    @property
    def jwt_expire_minutes(self) -> int:
        return self.env.int('JWT_EXPIRE_MINUTES', default=60)

    @property
    def jwt_sub(self) -> str:
        return self.env('JWT_SUB', default='g2b')

    @property
    def set_cookie_secure(self) -> bool:
        return self.env.bool('SET_COOKIE_SECURE', default=False)

    @property
    def set_cookie_samesite(self) -> str:
        return self.env('SET_COOKIE_SAMESITE', default='lax')

    # === Notion ===
    @property
    def notion_enabled(self) -> bool:
        return self.env.bool('NOTION_ENABLED', default=False)

    @property
    def notion_api_key(self) -> str:
        return self.env('NOTION_API_KEY', default='')

    @property
    def notion_database_id(self) -> str:
        return self.env('NOTION_DATABASE_ID', default='')

    @property
    def notion_min_score(self) -> int:
        return self.env.int('NOTION_MIN_SCORE', default=60)

    # === 파일 경로 ===
    @property
    def attachments_base_dir(self) -> str:
        return self.env('ATTACHMENTS_BASE_DIR',
            default='/mnt/c/Users/USER/OneDrive - 이용석/spotv/TRACKMAN/인수인계/베드민턴/g2b_agent/attachments')

    @property
    def output_base_dir(self) -> str:
        return self.env('OUTPUT_BASE_DIR',
            default='/mnt/c/Users/USER/OneDrive - 이용석/spotv/TRACKMAN/인수인계/베드민턴/g2b_agent/output')
