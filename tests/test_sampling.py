"""데이터 샘플링 엔진 테스트."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from p4.db.models import Base, RealtimeData, HistoryMin
from p4.sampling.engine import SamplingEngine
from p4.config import load_config


@pytest.fixture
def db_session(tmp_path):
    """테스트용 SQLite 인메모리 DB 세션."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session, engine
    session.close()
    engine.dispose()


@pytest.fixture
def populated_db(db_session):
    """샘플 데이터가 적재된 DB."""
    session, engine = db_session
    now = datetime.utcnow().replace(second=0, microsecond=0)
    period_start = now - timedelta(minutes=1)

    # TAG_A: 5개 값 (100, 102, 98, 104, 96) -> avg=100, min=96, max=104
    for i, val in enumerate([100.0, 102.0, 98.0, 104.0, 96.0]):
        session.add(RealtimeData(
            tag_name="TAG_A",
            value=val,
            quality=192,
            timestamp=period_start + timedelta(seconds=i * 10),
        ))

    # TAG_B: 3개 값 (50, 55, 45) -> avg=50, min=45, max=55
    for i, val in enumerate([50.0, 55.0, 45.0]):
        session.add(RealtimeData(
            tag_name="TAG_B",
            value=val,
            quality=192,
            timestamp=period_start + timedelta(seconds=i * 15),
        ))

    session.commit()
    return session, engine, period_start, now


class TestSamplingAggregation:
    """집계 로직 테스트."""

    def test_aggregate_avg(self, populated_db, monkeypatch, tmp_path):
        """평균값 계산 정확성."""
        session, engine, period_start, period_end = populated_db

        # 설정 생성
        cfg_file = tmp_path / "test.yaml"
        cfg_file.write_text('{"data": {"sampling_interval_min": 1}}', encoding="utf-8")
        config = load_config(cfg_file)

        # DB 연결을 테스트 엔진으로 교체
        import p4.db.connection as conn_module
        monkeypatch.setattr(conn_module, "_engine", engine)
        monkeypatch.setattr(conn_module, "_session_factory", sessionmaker(bind=engine, expire_on_commit=False))

        eng = SamplingEngine(config)
        count = eng._do_aggregate(period_start, period_end)

        assert count == 2  # TAG_A, TAG_B

        # 결과 확인
        results = session.query(HistoryMin).order_by(HistoryMin.tag_name).all()
        assert len(results) == 2

        tag_a = results[0]
        assert tag_a.tag_name == "TAG_A"
        assert abs(tag_a.avg_value - 100.0) < 0.01
        assert abs(tag_a.min_value - 96.0) < 0.01
        assert abs(tag_a.max_value - 104.0) < 0.01
        assert tag_a.sample_count == 5

        tag_b = results[1]
        assert tag_b.tag_name == "TAG_B"
        assert abs(tag_b.avg_value - 50.0) < 0.01
        assert tag_b.sample_count == 3

    def test_empty_period(self, db_session, monkeypatch, tmp_path):
        """데이터 없는 기간은 0개 레코드 생성."""
        session, engine = db_session
        cfg_file = tmp_path / "test.yaml"
        cfg_file.write_text("{}", encoding="utf-8")
        config = load_config(cfg_file)

        import p4.db.connection as conn_module
        monkeypatch.setattr(conn_module, "_engine", engine)
        monkeypatch.setattr(conn_module, "_session_factory", sessionmaker(bind=engine, expire_on_commit=False))

        eng = SamplingEngine(config)
        now = datetime.utcnow()
        count = eng._do_aggregate(now - timedelta(hours=1), now - timedelta(minutes=59))

        assert count == 0

    def test_std_calculation(self, populated_db, monkeypatch, tmp_path):
        """표준편차 계산 검증."""
        session, engine, period_start, period_end = populated_db
        cfg_file = tmp_path / "test.yaml"
        cfg_file.write_text("{}", encoding="utf-8")
        config = load_config(cfg_file)

        import p4.db.connection as conn_module
        monkeypatch.setattr(conn_module, "_engine", engine)
        monkeypatch.setattr(conn_module, "_session_factory", sessionmaker(bind=engine, expire_on_commit=False))

        eng = SamplingEngine(config)
        eng._do_aggregate(period_start, period_end)

        tag_a = session.query(HistoryMin).filter_by(tag_name="TAG_A").first()
        # [100, 102, 98, 104, 96] -> std ≈ 3.162
        assert tag_a.std_value is not None
        assert abs(tag_a.std_value - 3.162) < 0.01
