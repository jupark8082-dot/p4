"""
P4 데이터베이스 스키마 관리.

테이블 생성, 파티셔닝 설정, 초기 데이터 삽입을 담당한다.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

from p4.db.models import Base
from p4.db.connection import get_engine

logger = logging.getLogger(__name__)


def create_all_tables(engine: Engine | None = None) -> None:
    """모든 ORM 테이블을 생성한다.
    
    이미 존재하는 테이블은 건너뛴다 (checkfirst=True 기본 동작).
    """
    if engine is None:
        engine = get_engine()

    Base.metadata.create_all(engine)
    logger.info("All tables created successfully.")


def drop_all_tables(engine: Engine | None = None) -> None:
    """모든 테이블을 삭제한다. (주의: 개발/테스트 전용)"""
    if engine is None:
        engine = get_engine()

    Base.metadata.drop_all(engine)
    logger.info("All tables dropped.")


def create_mssql_partitions(engine: Engine) -> None:
    """MS SQL 환경에서 월별 파티셔닝을 설정한다.
    
    NOTE: SQLite에서는 실행하지 않는다.
    실제 MS SQL 배포 시에만 호출해야 한다.
    """
    url_str = str(engine.url)
    if "sqlite" in url_str:
        logger.info("Skipping partitioning for SQLite.")
        return

    partition_ddl = """
    -- 파티션 함수 생성 (월별)
    IF NOT EXISTS (
        SELECT 1 FROM sys.partition_functions WHERE name = 'pf_monthly'
    )
    BEGIN
        CREATE PARTITION FUNCTION pf_monthly (DATETIME)
        AS RANGE RIGHT FOR VALUES (
            '2026-01-01', '2026-02-01', '2026-03-01', '2026-04-01',
            '2026-05-01', '2026-06-01', '2026-07-01', '2026-08-01',
            '2026-09-01', '2026-10-01', '2026-11-01', '2026-12-01',
            '2027-01-01'
        );
    END;

    -- 파티션 스키마 생성
    IF NOT EXISTS (
        SELECT 1 FROM sys.partition_schemes WHERE name = 'ps_monthly'
    )
    BEGIN
        CREATE PARTITION SCHEME ps_monthly
        AS PARTITION pf_monthly ALL TO ([PRIMARY]);
    END;
    """

    try:
        with engine.connect() as conn:
            conn.execute(text(partition_ddl))
            conn.commit()
        logger.info("MS SQL partition function and scheme created.")
    except Exception as e:
        logger.warning(f"Partition creation skipped or failed: {e}")


def init_db(engine: Engine | None = None) -> None:
    """DB 초기화: 테이블 생성 + (MS SQL인 경우) 파티셔닝 설정."""
    if engine is None:
        engine = get_engine()
    
    create_all_tables(engine)
    create_mssql_partitions(engine)
    logger.info("Database initialization complete.")
