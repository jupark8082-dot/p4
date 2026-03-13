"""데이터베이스 모델 CRUD 테스트."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from p4.db.models import (
    Base, RealtimeData, HistoryMin, PredictResult,
    ModelInfo, User, LayoutConfig, DriftLog,
)


@pytest.fixture
def session():
    """테스트용 SQLite 인메모리 세션."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()
    engine.dispose()


class TestRealtimeData:
    def test_create_and_query(self, session):
        record = RealtimeData(
            tag_name="TEMP_BOILER",
            value=541.5,
            quality=192,
            timestamp=datetime.utcnow(),
        )
        session.add(record)
        session.commit()

        result = session.query(RealtimeData).first()
        assert result.tag_name == "TEMP_BOILER"
        assert abs(result.value - 541.5) < 0.01

    def test_multiple_tags(self, session):
        now = datetime.utcnow()
        for i in range(10):
            session.add(RealtimeData(
                tag_name=f"TAG_{i}",
                value=float(i * 10),
                timestamp=now + timedelta(seconds=i),
            ))
        session.commit()

        assert session.query(RealtimeData).count() == 10
        tag5 = session.query(RealtimeData).filter_by(tag_name="TAG_5").first()
        assert abs(tag5.value - 50.0) < 0.01


class TestHistoryMin:
    def test_create(self, session):
        now = datetime.utcnow().replace(second=0, microsecond=0)
        record = HistoryMin(
            tag_name="TEMP_BOILER",
            avg_value=540.0,
            min_value=538.0,
            max_value=543.0,
            std_value=1.2,
            sample_count=60,
            period_start=now - timedelta(minutes=1),
            period_end=now,
        )
        session.add(record)
        session.commit()

        result = session.query(HistoryMin).first()
        assert result.sample_count == 60
        assert abs(result.avg_value - 540.0) < 0.01


class TestModelInfo:
    def test_create(self, session):
        model = ModelInfo(
            model_name="model_lstm_temp_20260312",
            algorithm="LSTM",
            target_tag="TEMP_BOILER",
            input_tags='["FLOW_FEED", "PRESS_MAIN"]',
            rmse=2.5,
            status="active",
        )
        session.add(model)
        session.commit()

        result = session.query(ModelInfo).first()
        assert result.algorithm == "LSTM"
        assert result.status == "active"


class TestUser:
    def test_create(self, session):
        user = User(
            username="admin",
            hashed_password="$2b$12$hashed",
            full_name="관리자",
            role="admin",
        )
        session.add(user)
        session.commit()

        result = session.query(User).filter_by(username="admin").first()
        assert result.role == "admin"
        assert result.is_active is True


class TestPredictResult:
    def test_create(self, session):
        pred = PredictResult(
            tag_name="TEMP_BOILER",
            predicted_value=542.0,
            actual_value=541.5,
            deviation_pct=0.09,
            model_version="model_lstm_temp_20260312",
            prediction_time=datetime.utcnow() + timedelta(hours=1),
        )
        session.add(pred)
        session.commit()

        result = session.query(PredictResult).first()
        assert abs(result.predicted_value - 542.0) < 0.01


class TestDriftLog:
    def test_create(self, session):
        log = DriftLog(
            tag_name="TEMP_BOILER",
            psi_value=0.25,
            is_drifted=True,
            details='{"bins": 10}',
        )
        session.add(log)
        session.commit()

        result = session.query(DriftLog).first()
        assert result.is_drifted is True
        assert result.psi_value > 0.2
