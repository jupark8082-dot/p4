import torch
from torch.utils.data import Dataset
import numpy as np

class TimeSeriesDataset(Dataset):
    """
    발전소 시계열 데이터를 학습하기 위한 PyTorch Dataset.
    입력 시퀀스(history)를 통해 미래(horizon) 시점의 타겟 변수를 예측하도록 데이터를 구성.
    """
    def __init__(self, data_df, feature_cols, target_col, seq_length=60, horizon=60, scaler=None):
        """
        data_df: (N, D) 형태의 Pandas DataFrame (TB_HISTORY_MIN 데이터)
        feature_cols: 입력으로 사용할 태그 식별자 리스트
        target_col: 예측할 대상 태그 식별자
        seq_length: 과거 몇 스텝을 보고 예측할 것인지 (기본 60분)
        horizon: 몇 스텝 뒤의 미래를 예측할 것인지 (기본 60분 뒤)
        scaler: scikit-learn 류의 스케일러 인스턴스 (MinMaxScaler 등). 주어지지 않으면 내부적 정규화 없음.
        """
        self.seq_length = seq_length
        self.horizon = horizon
        self.target_col = target_col
        self.feature_cols = feature_cols
        
        # 스케일링 적용
        self.scaler = scaler
        if self.scaler is not None:
            # 보통 외부에서 fit()된 스케일러를 받아 transform 수행
            # 주의: data_df는 feature_cols 순서와 일치해야 함
            scaled_data = self.scaler.transform(data_df[self.feature_cols])
            self.data = scaled_data
        else:
            self.data = data_df[self.feature_cols].values

        # 타겟 인덱스 찾기
        self.target_idx = self.feature_cols.index(self.target_col)
        
        # 유효한 샘플 개수
        self.num_samples = len(self.data) - self.seq_length - self.horizon + 1

    def __len__(self):
        return max(0, self.num_samples)

    def __getitem__(self, idx):
        # 시간순으로 [idx : idx + seq_length] 만큼 X 수집
        x = self.data[idx : idx + self.seq_length]
        
        # 예측 대상 Y는 seq_length가 끝난 시점으로부터 horizon 만큼 지난 미래의 target_idx 값
        y = self.data[idx + self.seq_length + self.horizon - 1, self.target_idx]
        
        return torch.tensor(x, dtype=torch.float32), torch.tensor(y, dtype=torch.float32)

def create_windows(data, seq_length, horizon):
    """ 추론 전용 윈도우 생성 유틸 """
    pass
