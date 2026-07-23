"""개발 서버 실행 진입점.

  python run.py                # 기본 127.0.0.1:5000
  PORT=5001 python run.py      # 포트 변경 (Windows PowerShell: $env:PORT=5001; python run.py)

SocketIO 를 사용하므로 일반 app.run() 대신 socketio.run() 으로 구동한다.
"""
import os

from dotenv import load_dotenv

load_dotenv()  # .env 파일이 있으면 환경변수로 로드

from app import create_app
from app.extensions import socketio

app = create_app()

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    debug = app.config.get("DEBUG", False)

    # use_reloader=False:
    #   debug 모드의 자동 재시작(reloader)은 프로세스를 2개로 띄워 동일 포트를
    #   중복 바인딩하고, SocketIO 개발 서버와 함께 쓰면 요청이 멈추는 문제가 있다.
    #   개발 편의(코드 변경 시 자동 재시작)보다 안정적 구동을 우선해 끈다.
    # allow_unsafe_werkzeug=True:
    #   Werkzeug 개발 서버로 SocketIO 를 구동하도록 허용(로컬 개발 전용).
    socketio.run(
        app,
        host=host,
        port=port,
        debug=debug,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )
