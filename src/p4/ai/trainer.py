import os
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from datetime import datetime

class AITrainer:
    def __init__(self, models_dict, device='cpu'):
        """
        models_dict: {"LSTM": model_instance1, "GRU": model_instance2}
        """
        self.models = models_dict
        self.device = torch.device(device)
        self.criterion = nn.MSELoss()
        
    def train_single_model(self, name, model, train_loader, val_loader, epochs, lr):
        model.to(self.device)
        optimizer = optim.Adam(model.parameters(), lr=lr)
        
        best_val_loss = float('inf')
        
        for epoch in range(epochs):
            model.train()
            train_loss = 0.0
            for X_batch, y_batch in train_loader:
                X_batch, y_batch = X_batch.to(self.device), y_batch.to(self.device)
                
                optimizer.zero_grad()
                predictions = model(X_batch)
                loss = self.criterion(predictions, y_batch)
                
                loss.backward()
                optimizer.step()
                train_loss += loss.item() * X_batch.size(0)
                
            train_loss /= len(train_loader.dataset)
            
            # Validation
            model.eval()
            val_loss = 0.0
            with torch.no_grad():
                for X_batch, y_batch in val_loader:
                    X_batch, y_batch = X_batch.to(self.device), y_batch.to(self.device)
                    predictions = model(X_batch)
                    loss = self.criterion(predictions, y_batch)
                    val_loss += loss.item() * X_batch.size(0)
            val_loss /= len(val_loader.dataset)
            
            # RMSE calculation
            val_rmse = val_loss ** 0.5
            
            if val_rmse < best_val_loss:
                best_val_loss = val_rmse
                
        print(f"[{name}] Best Validation RMSE: {best_val_loss:.4f}")
        return model, best_val_loss

    def find_best_model(self, train_loader, val_loader, epochs=10, lr=0.001):
        """
        여러 아키텍처를 순회하며 학습하고 가장 에러가 적은 모델과 அதன் RMSE를 반환
        """
        best_rmse = float('inf')
        best_model = None
        best_name = ""
        
        results = {}
        for name, model in self.models.items():
            print(f"--- Training {name} ---")
            trained_model, val_rmse = self.train_single_model(name, model, train_loader, val_loader, epochs, lr)
            results[name] = val_rmse
            
            if val_rmse < best_rmse:
                best_rmse = val_rmse
                best_model = trained_model
                best_name = name
                
        print(f"\n=> Auto-Selected Best Model: {best_name} (RMSE: {best_rmse:.4f})")
        return best_name, best_model, best_rmse
        
    def export_to_onnx(self, model, dummy_input, save_path):
        """
        최종 선정된 최고 성능 모델을 ONNX 런타임 추론용으로 변환
        dummy_input: (Batch, Seq, Features) 형태의 텐서
        """
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        model.eval()
        torch.onnx.export(
            model, 
            dummy_input.to(self.device), 
            save_path, 
            export_params=True, 
            opset_version=14, 
            do_constant_folding=True, 
            input_names=['input'], 
            output_names=['output'],
            dynamic_axes={'input': {0: 'batch_size'}, 'output': {0: 'batch_size'}}
        )
        print(f"Model exported to ONNX format at: {save_path}")
