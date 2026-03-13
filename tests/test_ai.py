import os
import torch
import numpy as np
import pandas as pd
from p4.ai.dataset import TimeSeriesDataset
from p4.ai.models import LightLSTM, LightGRU
from p4.ai.trainer import AITrainer
from p4.ai.inferencer import ONNXInferencer
from p4.ai.manager import ModelManager

def test_dataset_sequence_generation():
    # 100행의 임의 시계열 데이터 생성
    np.random.seed(42)
    dummy_data = np.random.rand(100, 3) 
    df = pd.DataFrame(dummy_data, columns=['TAG_A', 'TAG_B', 'TAG_C'])
    
    # seq_length=60, horizon=5 인 경우
    # 100 - 60 - 5 + 1 = 36개의 샘플이 생성되어야 함
    dataset = TimeSeriesDataset(
        data_df=df, 
        feature_cols=['TAG_A', 'TAG_B', 'TAG_C'], 
        target_col='TAG_A', 
        seq_length=60, 
        horizon=5
    )
    
    assert len(dataset) == 36
    x, y = dataset[0]
    
    # x shape = (60, 3)
    assert x.shape == (60, 3)
    # y shape = 스칼라
    assert y.dim() == 0

def test_trainer_and_onnx_export(tmp_path):
    # 가상의 DataLoader (1배치, 60시퀀스, 3피처)
    X = torch.randn(10, 60, 3)
    y = torch.randn(10)
    train_dataset = torch.utils.data.TensorDataset(X, y)
    train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=2)
    
    models = {
        "LSTM": LightLSTM(input_dim=3, hidden_dim=16),
        "GRU": LightGRU(input_dim=3, hidden_dim=16)
    }
    
    trainer = AITrainer(models_dict=models, device='cpu')
    best_name, best_model, best_rmse = trainer.find_best_model(train_loader, train_loader, epochs=1)
    
    assert best_name in ["LSTM", "GRU"]
    assert best_model is not None
    
    # ONNX Export 기능 테스트
    export_path = str(tmp_path / "test_model.onnx")
    dummy_input = torch.randn(1, 60, 3)
    trainer.export_to_onnx(best_model, dummy_input, export_path)
    
    assert os.path.exists(export_path)
    
def test_onnx_inference(tmp_path):
    # 위 테스트에서 생성된 모델을 로드하여 추론해보기
    model = LightLSTM(input_dim=2, hidden_dim=8)
    model.eval()
    
    export_path = str(tmp_path / "infer_test.onnx")
    dummy_input = torch.randn(1, 60, 2)
    torch.onnx.export(model, dummy_input, export_path, input_names=['input'], output_names=['output'], dynamic_axes={'input': {0: 'batch_size'}})
    
    inferencer = ONNXInferencer()
    
    # Nump Array 생성
    import numpy as np
    test_input = np.random.rand(1, 60, 2).astype(np.float32)
    
    result = inferencer.predict("TEST_TAG", export_path, test_input)
    assert isinstance(result, float)
