"""Deadband 필터링 테스트."""

import pytest

from p4.opc.deadband import DeadbandFilter


class TestDeadbandPercent:
    """퍼센트 기반 Deadband 테스트."""

    def setup_method(self):
        self.db = DeadbandFilter(default_type="percent", default_threshold=1.0)  # 1%

    def test_first_value_always_saves(self):
        assert self.db.should_save("TAG1", 100.0) is True

    def test_small_change_skips(self):
        self.db.should_save("TAG1", 100.0)
        # 0.5% 변화 -> 1% 미만 -> skip
        assert self.db.should_save("TAG1", 100.5) is False

    def test_large_change_saves(self):
        self.db.should_save("TAG1", 100.0)
        # 2% 변화 -> 1% 초과 -> save
        assert self.db.should_save("TAG1", 102.0) is True

    def test_negative_change_saves(self):
        self.db.should_save("TAG1", 100.0)
        # -1.5% 변화 -> save
        assert self.db.should_save("TAG1", 98.5) is True

    def test_independent_tags(self):
        """서로 다른 태그는 독립적으로 판정된다."""
        self.db.should_save("TAG1", 100.0)
        self.db.should_save("TAG2", 200.0)
        # TAG1: 미변화, TAG2: 큰 변화
        assert self.db.should_save("TAG1", 100.3) is False
        assert self.db.should_save("TAG2", 210.0) is True

    def test_zero_last_value_fallback(self):
        """마지막 값이 0일 때 절대값 비교로 폴백."""
        self.db.should_save("TAG1", 0.0)
        # 절대값 0.5 < threshold 1.0 -> skip
        assert self.db.should_save("TAG1", 0.5) is False
        # 절대값 1.5 > threshold 1.0 -> save
        assert self.db.should_save("TAG1", 1.5) is True


class TestDeadbandAbsolute:
    """절대값 기반 Deadband 테스트."""

    def setup_method(self):
        self.db = DeadbandFilter(default_type="absolute", default_threshold=2.0)

    def test_small_change_skips(self):
        self.db.should_save("TAG1", 100.0)
        assert self.db.should_save("TAG1", 101.0) is False  # 1.0 < 2.0

    def test_large_change_saves(self):
        self.db.should_save("TAG1", 100.0)
        assert self.db.should_save("TAG1", 103.0) is True  # 3.0 > 2.0


class TestDeadbandOverrides:
    """태그별 개별 설정 테스트."""

    def test_override_threshold(self):
        db = DeadbandFilter(default_type="percent", default_threshold=1.0)
        db.set_override("CRITICAL_TAG", "percent", 0.1)  # 더 엄격한 임계값

        db.should_save("CRITICAL_TAG", 100.0)
        # 0.5% 변화 -> 기본 1%에서는 skip이지만, 오버라이드 0.1%에서는 save
        assert db.should_save("CRITICAL_TAG", 100.5) is True

    def test_override_type(self):
        db = DeadbandFilter(default_type="percent", default_threshold=1.0)
        db.set_override("ABS_TAG", "absolute", 5.0)

        db.should_save("ABS_TAG", 100.0)
        # 절대값 3.0 < 5.0 -> skip
        assert db.should_save("ABS_TAG", 103.0) is False


class TestDeadbandReset:
    """캐시 초기화 테스트."""

    def test_reset_single_tag(self):
        db = DeadbandFilter(default_type="percent", default_threshold=1.0)
        db.should_save("TAG1", 100.0)
        db.should_save("TAG2", 200.0)

        db.reset("TAG1")
        # TAG1은 리셋되어 다음 값이 첫 값으로 취급
        assert db.should_save("TAG1", 100.0) is True
        # TAG2는 유지
        assert db.should_save("TAG2", 200.3) is False

    def test_reset_all(self):
        db = DeadbandFilter(default_type="percent", default_threshold=1.0)
        db.should_save("TAG1", 100.0)
        db.should_save("TAG2", 200.0)

        db.reset()
        assert db.should_save("TAG1", 100.0) is True
        assert db.should_save("TAG2", 200.0) is True
