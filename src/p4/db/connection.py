"""
P4 데이터베이스 연결 관리.

SQLAlchemy 엔진, 세션 팩토리, 커넥션 풀링을 제공한다.
MS SQL과 SQLite 모두 지원.
"""

from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine

from p4.config import get_config, AppConfig


_engine: Engine | None = None
_session_factory: sessionmaker | None = None


def _create_engine(config: AppConfig) -> Engine:
    """설정 기반으로 SQLAlchemy 엔진을 생성한다."""
    url = config.database.url

    connect_args = {}
    kwargs = {
        "echo": config.database.echo,
    }

    if url.startswith("sqlite"):
        # SQLite: WAL 모드 + 동시성 개선
        connect_args["check_same_thread"] = False
    else:
        # MS SQL: 커넥션 풀링
        kwargs["pool_size"] = config.database.pool_size
        kwargs["max_overflow"] = config.database.max_overflow
        kwargs["pool_pre_ping"] = True  # 끊어진 연결 감지
        kwargs["pool_recycle"] = 3600   # 1시간마다 커넥션 재생성

    engine = create_engine(url, connect_args=connect_args, **kwargs)

    # SQLite WAL 모드 활성화
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, _connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    return engine


def get_engine(config: AppConfig | None = None) -> Engine:
    """싱글턴 엔진 인스턴스를 반환한다."""
    global _engine
    if _engine is None:
        if config is None:
            config = get_config()
        _engine = _create_engine(config)
    return _engine


def get_session_factory(config: AppConfig | None = None) -> sessionmaker:
    """싱글턴 세션 팩토리를 반환한다."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine(config)
        _session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return _session_factory


def get_session(config: AppConfig | None = None) -> Session:
    """새로운 세션을 생성하여 반환한다. with 문으로 사용 권장."""
    factory = get_session_factory(config)
    return factory()


def reset_engine() -> None:
    """엔진 및 세션 팩토리를 리셋한다. (테스트용)"""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
