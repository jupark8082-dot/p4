# P4 - AI-Powered Power Plant Performance Predictor

발전소 OPC DA 실시간 운전/성능 데이터를 통합하고, 딥러닝 모델을 통해 미래 성능 지표를 예측하여 계통도 기반 웹 대시보드로 제공하는 시스템입니다.

## Quick Start

### 1. 환경 설정

```bash
cd d:/project/p4
pip install -e ".[dev]"
```

### 2. 시뮬레이터 모드 실행

```bash
python -m p4.main --simulate
```

### 3. 테스트 실행

```bash
python -m pytest tests/ -v
```

## 프로젝트 구조

```
p4/
├── config/defaults.yaml     # 전체 기본값 설정
├── src/p4/                  # 메인 패키지
│   ├── config.py            # 설정 로더
│   ├── db/                  # 데이터베이스
│   ├── opc/                 # OPC DA 모듈
│   ├── sampling/            # 데이터 샘플링
│   └── main.py              # 진입점
└── tests/                   # 테스트
```

## 설정 변경

`config/defaults.yaml` 파일에서 모든 기본값을 관리합니다. 환경변수로도 오버라이드 가능합니다:

```bash
set P4_DATABASE__URL=mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+17+for+SQL+Server
```
