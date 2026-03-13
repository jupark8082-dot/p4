"""
P4 Deadband 필터링 모듈.

태그별 변화량이 임계값 미만인 경우 데이터 저장을 건너뛴다.
이를 통해 DB 부하를 크게 줄인다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DeadbandFilter:
    """태그별 Deadband 필터.
    
    지원하는 타입:
    - percent: |new - last| / |last| * 100 > threshold 이면 저장
    - absolute: |new - last| > threshold 이면 저장
    
    Attributes:
        default_type: 기본 Deadband 타입 ("percent" 또는 "absolute")
        default_threshold: 기본 임계값
        tag_overrides: 태그별 개별 임계값 설정
        _last_values: 태그별 마지막 저장 값 캐시
    """

    default_type: str = "percent"
    default_threshold: float = 0.5
    tag_overrides: dict[str, dict] = field(default_factory=dict)
    _last_values: dict[str, float] = field(default_factory=dict, repr=False)

    def should_save(self, tag_name: str, new_value: float) -> bool:
        """새 값을 저장해야 하는지 판단한다.
        
        Args:
            tag_name: 태그명
            new_value: 새로운 측정값
            
        Returns:
            True이면 저장, False이면 건너뜀
        """
        # 첫 번째 값은 항상 저장
        if tag_name not in self._last_values:
            self._last_values[tag_name] = new_value
            return True

        last_value = self._last_values[tag_name]

        # 태그별 오버라이드 확인
        override = self.tag_overrides.get(tag_name, {})
        db_type = override.get("type", self.default_type)
        threshold = override.get("threshold", self.default_threshold)

        if db_type == "percent":
            passed = self._check_percent(last_value, new_value, threshold)
        elif db_type == "absolute":
            passed = self._check_absolute(last_value, new_value, threshold)
        else:
            logger.warning(f"Unknown deadband type '{db_type}' for {tag_name}, saving anyway.")
            passed = True

        if passed:
            self._last_values[tag_name] = new_value

        return passed

    def reset(self, tag_name: str | None = None) -> None:
        """캐시된 마지막 값을 초기화한다.
        
        Args:
            tag_name: 지정 시 해당 태그만 초기화, None이면 전체 초기화
        """
        if tag_name is None:
            self._last_values.clear()
        else:
            self._last_values.pop(tag_name, None)

    def set_override(self, tag_name: str, db_type: str, threshold: float) -> None:
        """특정 태그에 개별 Deadband 설정을 적용한다."""
        self.tag_overrides[tag_name] = {"type": db_type, "threshold": threshold}

    @staticmethod
    def _check_percent(last: float, new: float, threshold: float) -> bool:
        """퍼센트 기반 판정."""
        if abs(last) < 1e-10:
            # 마지막 값이 0에 극히 가까우면 절대값 비교로 폴백
            return abs(new - last) > threshold
        change_pct = abs(new - last) / abs(last) * 100.0
        return change_pct > threshold

    @staticmethod
    def _check_absolute(last: float, new: float, threshold: float) -> bool:
        """절대값 기반 판정."""
        return abs(new - last) > threshold
