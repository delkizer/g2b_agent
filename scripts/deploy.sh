#!/usr/bin/env bash
set -e

# hostname 기반 환경 자동 감지
CURRENT_HOSTNAME=$(hostname)
echo "현재 서버: $CURRENT_HOSTNAME"

# 환경 판별
if [[ "$CURRENT_HOSTNAME" == "bxl-test-db" ]] || [[ "$CURRENT_HOSTNAME" == *"test"* ]]; then
    ENVIRONMENT="dev"
    TARGET_DIR="/var/www/g2b-dev"
    echo "개발환경으로 감지되었습니다."
else
    echo "ERROR: 알 수 없는 서버환경입니다: $CURRENT_HOSTNAME"
    echo "지원되는 환경:"
    echo "  - 개발: bxl-test-db, *test*"
    exit 1
fi

# 운영환경 블록 (향후 활성화)
# elif [[ "$CURRENT_HOSTNAME" == "g2b-prod" ]]; then
#     ENVIRONMENT="prod"
#     TARGET_DIR="/var/www/g2b"
#     echo "운영환경으로 감지되었습니다."
#
#     # 운영환경 안전장치
#     echo "WARNING: 운영환경에 배포하시겠습니까? (y/N)"
#     read -r CONFIRM
#     if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
#         echo "배포를 취소했습니다."
#         exit 0
#     fi

echo "배포 대상 디렉토리: $TARGET_DIR"
echo ""

# 환경 사전 준비
echo "환경 사전 준비 중..."

# 로그 디렉토리 보장
mkdir -p ~/work/logs/g2b_server
echo "  - 로그 디렉토리 확인: ~/work/logs/g2b_server"

# 파일 저장 디렉토리 보장
mkdir -p ~/data/g2b/attachments
mkdir -p ~/data/g2b/output
echo "  - 파일 저장 디렉토리 확인: ~/data/g2b/{attachments,output}"

# RSA 키 자동 생성 (없으면)
KEY_DIR=~/work/g2b_agent/server/server_env/rsa256
if [ ! -f "$KEY_DIR/private_key.pem" ]; then
    echo "  - RSA 키 생성 중..."
    mkdir -p "$KEY_DIR"
    openssl genrsa -out "$KEY_DIR/private_key.pem" 2048
    openssl rsa -in "$KEY_DIR/private_key.pem" -pubout -out "$KEY_DIR/public_key.pem"
    chmod 600 "$KEY_DIR/private_key.pem"
    chmod 644 "$KEY_DIR/public_key.pem"
    echo "  - RSA 키 생성 완료: $KEY_DIR"
else
    echo "  - RSA 키 존재 확인: $KEY_DIR"
fi

echo ""

# 소스 최신화
echo "소스 코드 최신화 중..."
cd ~/work/g2b_agent
git pull origin main

# Server 의존성 설치
echo "Server 의존성 설치 중..."
cd ~/work/g2b_agent/server
.venv/bin/pip install -q -r requirements.txt

# Frontend 빌드
echo "Frontend 빌드 시작..."
cd ~/work/g2b_agent/frontend
npm ci

# 환경별 빌드 명령 실행
if [[ "$ENVIRONMENT" == "dev" ]]; then
    echo "개발환경 빌드 실행 (.env.development)..."
    npm run build:dev
else
    echo "운영환경 빌드 실행 (.env.production)..."
    npm run build:prod
fi

# 배포
echo "Frontend 배포 중..."
sudo rm -rf $TARGET_DIR/*
sudo cp -r dist/* $TARGET_DIR/
sudo chown -R www-data:www-data $TARGET_DIR
sudo chmod -R 755 $TARGET_DIR

echo "Frontend 배포 완료: $TARGET_DIR"

# 서비스 재시작
echo "g2b_server 재시작 중..."
sudo systemctl restart g2b_server

echo "Nginx 재시작 중..."
sudo systemctl reload nginx

echo ""
echo "배포가 성공적으로 완료되었습니다!"
echo "환경: $ENVIRONMENT"
echo "서버: $CURRENT_HOSTNAME"
