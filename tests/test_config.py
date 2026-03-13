"""설정 관리 모듈 테스트."""

import os
import tempfile
from pathlib import Path

import yaml
import pytest

from p4.config import load_config, AppConfig, _apply_env_overrides


class TestLoadConfig:
    """YAML 설정 로딩 테스트."""

    def test_default_values(self, tmp_path: Path):
        """빈 YAML 파일에서도 기본값이 적용되는지 확인."""
        cfg_file = tmp_path / "empty.yaml"
        cfg_file.write_text("{}", encoding="utf-8")
        config = load_config(cfg_file)

        assert isinstance(config, AppConfig)
        assert config.data.sampling_interval_min == 1
        assert config.prediction.inference_interval_min == 5
        assert config.model.default_algorithm == "LSTM"
        assert config.web.port == 8000

    def test_yaml_override(self, tmp_path: Path):
        """YAML 값이 기본값을 오버라이드하는지 확인."""
        cfg_file = tmp_path / "custom.yaml"
        cfg_data = {
            "data": {"sampling_interval_min": 5},
            "web": {"port": 9000},
        }
        cfg_file.write_text(yaml.dump(cfg_data), encoding="utf-8")
        config = load_config(cfg_file)

        assert config.data.sampling_interval_min == 5
        assert config.web.port == 9000
        # 변경하지 않은 항목은 기본값 유지
        assert config.prediction.inference_interval_min == 5

    def test_nonexistent_file(self, tmp_path: Path):
        """존재하지 않는 파일은 기본값으로 로딩."""
        config = load_config(tmp_path / "nonexistent.yaml")
        assert config.data.sampling_interval_min == 1

    def test_simulator_tags(self, tmp_path: Path):
        """시뮬레이터 태그 설정이 파싱되는지 확인."""
        cfg_data = {
            "simulator": {
                "tags": [
                    {"name": "TEMP_1", "unit": "°C", "base_value": 100.0, "noise_amplitude": 2.0},
                    {"name": "PRESS_1", "unit": "MPa", "base_value": 10.0},
                ]
            }
        }
        cfg_file = tmp_path / "sim.yaml"
        cfg_file.write_text(yaml.dump(cfg_data), encoding="utf-8")
        config = load_config(cfg_file)

        assert len(config.simulator.tags) == 2
        assert config.simulator.tags[0].name == "TEMP_1"
        assert config.simulator.tags[1].noise_amplitude == 1.0  # 기본값


class TestEnvOverrides:
    """환경변수 오버라이드 테스트."""

    def test_string_override(self):
        data = {"database": {"url": "sqlite:///old.db"}}
        os.environ["P4_DATABASE__URL"] = "sqlite:///new.db"
        try:
            result = _apply_env_overrides(data)
            assert result["database"]["url"] == "sqlite:///new.db"
        finally:
            del os.environ["P4_DATABASE__URL"]

    def test_int_override(self):
        data = {"web": {"port": 8000}}
        os.environ["P4_WEB__PORT"] = "9999"
        try:
            result = _apply_env_overrides(data)
            assert result["web"]["port"] == 9999
            assert isinstance(result["web"]["port"], int)
        finally:
            del os.environ["P4_WEB__PORT"]

    def test_bool_override(self):
        data = {"database": {"echo": False}}
        os.environ["P4_DATABASE__ECHO"] = "true"
        try:
            result = _apply_env_overrides(data)
            assert result["database"]["echo"] is True
        finally:
            del os.environ["P4_DATABASE__ECHO"]
