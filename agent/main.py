"""에이전트 진입점 (uvicorn)

uvicorn으로 FastAPI 서버를 시작한다.
loguru 설정은 server.py lifespan에서 수행하므로 여기서는 호출하지 않는다.

사용법:
    cd agent/
    python main.py

참조:
- docs/pipeline/04-entry-point.md §2.4 : lifespan 방식 진입점
- agent/server.py : FastAPI 앱 + lifespan (setup_logger 포함)
"""

import uvicorn


def main():
    uvicorn.run(
        "server:app",
        host="127.0.0.1",
        port=8100,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
