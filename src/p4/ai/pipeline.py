import logging
from datetime import datetime, timedelta
import torch
from torch.utils.data import DataLoader
from sqlalchemy import select

from p4.config import get_config
from p4.db.connection import get_session
from p4.db.models import HistoryMin
from p4.ai.dataset import TimeSeriesDataset
from p4.ai.models import LightLSTM, LightGRU
from p4.ai.trainer import AITrainer
from p4.ai.manager import ModelManager

logger = logging.getLogger(__name__)

class TrainingPipeline:
    def __init__(self, config=None):
        self._config = config or get_config()
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.manager = ModelManager(models_dir=self._config.model.model_dir, max_keep=self._config.model.max_versions)
        self.seq_len = self._config.prediction.input_sequence_length
        self.horizon = self._config.prediction.forecast_horizon_min

    def get_training_data(self, target_tag: str, feature_tags: list[str], days_back: int = 14):
        """DB에서 학습 데이터를 로드해 Pandas DataFrame으로 변환 (보통 수동 스케일링 권장하지만 지금은 단순화)"""
        session = get_session(self._config)
        try:
            cutoff = datetime.utcnow() - timedelta(days=days_back)
            
            # 여기서 실제로는 여러 태그를 Group By / Pivot 등의 Pandas 트릭으로 
            # (Timestamp, Tag1, Tag2... TargetTag) 행렬로 만들어야 함.
            # 지금은 간단화를 위해 Target 태그 하나에 대해서만 자가 예측을 수행하도록 임시 구성.
            
            query = select(HistoryMin.period_start, HistoryMin.avg_value).where(
                HistoryMin.tag_name == target_tag,
                HistoryMin.period_start >= cutoff
            ).order_by(HistoryMin.period_start.asc())
            
            results = session.execute(query).all()
            if not results:
                return None
                
            import pandas as pd
            df = pd.DataFrame(results, columns=['period_start', target_tag])
            
            # 입력 피처 개수가 1개(target 자기 자신)
            return df
        finally:
            session.close()

    def run(self, target_tag: str):
        logger.info(f"Starting training pipeline for {target_tag}")
        
        # 1. 데이터 로드 (간소화: 자기 자신의 과거 데이터로 단변량 예측 수행)
        df = self.get_training_data(target_tag, feature_tags=[target_tag])
        if df is None or len(df) <= self.seq_len + self.horizon:
            logger.warning(f"Not enough data to train model for {target_tag}")
            return False

        # 2. 전처리 스케일러 (MinMax 적용은 향후)
        # 3. 데이터셋 및 로더 구성
        dataset = TimeSeriesDataset(
            data_df=df,
            feature_cols=[target_tag],
            target_col=target_tag,
            seq_length=self.seq_len,
            horizon=self.horizon,
            scaler=None  # 간단화를 위해 None
        )
        
        # 8:2 Split
        train_size = int(0.8 * len(dataset))
        val_size = len(dataset) - train_size
        train_dataset, val_dataset = torch.utils.data.random_split(dataset, [train_size, val_size])
        
        train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)

        # 4. 모델 준비
        input_dim = 1 # 현재 단변량 예측
        models = {
            "LSTM": LightLSTM(input_dim=input_dim, hidden_dim=16, output_dim=1),
            "GRU": LightGRU(input_dim=input_dim, hidden_dim=16, output_dim=1)
        }

        # 5. 학습 및 최고 모델 탐색
        trainer = AITrainer(models_dict=models, device=self.device)
        best_name, best_model, best_rmse = trainer.find_best_model(train_loader, val_loader, epochs=5)

        logger.info(f"Training finished. Best Model: {best_name}, RMSE: {best_rmse}")

        # 6. ONNX 내보내기 및 매니저 저장
        save_path = self.manager.generate_save_path(target_tag, best_name)
        dummy_input = torch.randn(1, self.seq_len, input_dim)
        trainer.export_to_onnx(best_model, dummy_input, save_path)
        
        # 7. 이전 모델 정리 (맥스 킵 초과 분)
        self.manager.cleanup_old_models(target_tag)

        logger.info(f"Pipeline completed successfully. Output model: {save_path}")
        return True
