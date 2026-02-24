"""사용자 SQLAlchemy 모델"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, text
from models.announcement import Base


class User(Base):
    """관리자 사용자 모델"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, comment="로그인 아이디")
    password_hash = Column(String(200), nullable=False, comment="bcrypt 해시")
    display_name = Column(String(100), comment="표시명")
    is_active = Column(Boolean, nullable=False, default=True,
                       server_default="true", comment="활성 여부")
    refresh_token = Column(String(1000), comment="JWT Refresh Token")
    token_expire_at = Column(DateTime(timezone=True), comment="Refresh Token 만료일시")
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=text("NOW()"), comment="생성 시각")

    __table_args__ = (
        {"schema": "g2b"},
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}')>"
