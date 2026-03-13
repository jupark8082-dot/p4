import torch
import torch.nn as nn

class LightLSTM(nn.Module):
    """
    CPU 기반 추론 최적화를 위한 경량 LSTM 트렌드 예측 모델
    """
    def __init__(self, input_dim, hidden_dim=64, num_layers=2, output_dim=1, dropout=0.1):
        super(LightLSTM, self).__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        
        # batch_first=True : (Batch, Seq, Feature) 형태로 데이터 입력
        self.lstm = nn.LSTM(
            input_size=input_dim, 
            hidden_size=hidden_dim, 
            num_layers=num_layers, 
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0
        )
        
        # 마지막 타임스텝의 hidden state를 스칼라 출력으로 선형 변환
        self.fc = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        # x shape: (Batch Size, Sequence Length, Input Dim)
        
        # lstm_out shape: (Batch, Seq, Hidden)
        # hidden_state shape: (num_layers, Batch, Hidden)
        lstm_out, (hidden_state, cell_state) = self.lstm(x)
        
        # 마지막 타임스텝의 출력 벡터(lstm_out[:, -1, :])를 사용하여 예측
        last_out = lstm_out[:, -1, :] 
        
        # (Batch, 1) 형태의 예측 결과 반환
        return self.fc(last_out).squeeze(-1)

class LightGRU(nn.Module):
    """ 향후 최적 모델 추천용 GRU 아키텍처 """
    def __init__(self, input_dim, hidden_dim=64, num_layers=2, output_dim=1, dropout=0.1):
        super(LightGRU, self).__init__()
        self.gru = nn.GRU(
            input_size=input_dim, 
            hidden_size=hidden_dim, 
            num_layers=num_layers, 
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0
        )
        self.fc = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        out, _ = self.gru(x)
        return self.fc(out[:, -1, :]).squeeze(-1)
