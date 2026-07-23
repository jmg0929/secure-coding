"""공유 확장 인스턴스 (순환 import 방지를 위해 별도 모듈로 분리)."""
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_socketio import SocketIO

csrf = CSRFProtect()

# 브루트포스/남용 완화를 위한 요청 속도 제한
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["300 per hour"],
)

# 실시간 채팅. async_mode 는 기본(threading) 사용.
socketio = SocketIO(cors_allowed_origins=[])  # 동일 출처만 허용
