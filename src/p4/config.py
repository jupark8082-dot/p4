"""
P4 설정 관리 모듈.

config/defaults.yaml을 기반으로 Pydantic 모델을 통해 타입 안전한 설정을 제공한다.
환경변수 오버라이드 지원: P4_DATABASE__URL, P4_OPC__HOST 등 (이중 밑줄로 중첩 구분)
"""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache
from typing import Optional

import yaml
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 프로젝트 루트 경로 탐색
# ---------------------------------------------------------------------------

def _find_project_root() -> Path:
    """config/ 디렉토리가 있는 프로젝트 루트를 탐색한다."""
    current = Path(__file__).resolve().parent
    for _ in range(5):
        if (current / "config" / "defaults.yaml").exists():
            return current
        current = current.parent
    # 폴백: 현재 작업 디렉토리
    return Path.cwd()


PROJECT_ROOT = _find_project_root()


# ---------------------------------------------------------------------------
# 설정 모델 정의
# ---------------------------------------------------------------------------

class DatabaseConfig(BaseModel):
    url: str = "sqlite:///data/p4.db"
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False


class DataConfig(BaseModel):
    sampling_interval_min: int = 1
    realtime_retention_hours: int = 24
    history_retention_years: int = 2


class OpcConfig(BaseModel):
    host: str = "localhost"
    prog_id: str = "Matrikon.OPC.Simulation.1"
    update_rate_ms: int = 1000
    reconnect_max_retries: int = 5
    reconnect_base_delay_sec: int = 2


class DeadbandConfig(BaseModel):
    default_type: str = "percent"   # percent | absolute
    default_threshold: float = 0.5


class PredictionConfig(BaseModel):
    inference_interval_min: int = 5
    forecast_horizon_min: int = 60
    input_sequence_length: int = 60


class ModelConfig(BaseModel):
    default_algorithm: str = "LSTM"
    max_versions: int = 5
    training_schedule: str = "0 2 * * *"
    model_dir: str = "models/"


class DriftConfig(BaseModel):
    method: str = "PSI"
    threshold: float = 0.2
    check_interval_days: int = 7


class WebConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    max_trend_charts: int = 4
    deviation_warn_pct: float = 5.0
    deviation_alert_pct: float = 10.0


class AuthConfig(BaseModel):
    secret_key: str = "CHANGE-ME-IN-PRODUCTION-USE-RANDOM-SECRET"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480


class SimulatorTagConfig(BaseModel):
    name: str
    unit: str = ""
    base_value: float = 100.0
    noise_amplitude: float = 1.0


class SimulatorConfig(BaseModel):
    enabled: bool = True
    num_tags: int = 20
    base_interval_sec: int = 1
    tags: list[SimulatorTagConfig] = Field(default_factory=list)


class AppConfig(BaseModel):
    """P4 전체 설정."""
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    opc: OpcConfig = Field(default_factory=OpcConfig)
    deadband: DeadbandConfig = Field(default_factory=DeadbandConfig)
    prediction: PredictionConfig = Field(default_factory=PredictionConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    drift: DriftConfig = Field(default_factory=DriftConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    simulator: SimulatorConfig = Field(default_factory=SimulatorConfig)


# ---------------------------------------------------------------------------
# 설정 로딩
# ---------------------------------------------------------------------------

def _apply_env_overrides(data: dict, prefix: str = "P4") -> dict:
    """환경변수로 설정을 오버라이드한다.
    
    예) P4_DATABASE__URL -> data["database"]["url"]
    """
    for key, value in os.environ.items():
        if not key.startswith(f"{prefix}_"):
            continue
        parts = key[len(prefix) + 1:].lower().split("__")
        target = data
        for part in parts[:-1]:
            if part not in target:
                target[part] = {}
            target = target[part]
        # 타입 보존: 숫자/불리언 변환 시도
        final_key = parts[-1]
        if value.lower() in ("true", "false"):
            target[final_key] = value.lower() == "true"
        else:
            try:
                target[final_key] = int(value)
            except ValueError:
                try:
                    target[final_key] = float(value)
                except ValueError:
                    target[final_key] = value
    return data


def load_config(config_path: Optional[str | Path] = None) -> AppConfig:
    """YAML 설정 파일을 로딩하고 AppConfig 인스턴스를 반환한다."""
    if config_path is None:
        config_path = PROJECT_ROOT / "config" / "defaults.yaml"
    else:
        config_path = Path(config_path)

    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    else:
        raw = {}

    raw = _apply_env_overrides(raw)
    return AppConfig(**raw)


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """싱글턴 설정 인스턴스를 반환한다. (캐시됨)"""
    return load_config()
