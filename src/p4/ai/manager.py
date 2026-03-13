import os
import glob
from datetime import datetime

class ModelManager:
    """
    학습된 ONNX 모델 보관, 로드 및 이력 관리를 담당
    """
    def __init__(self, models_dir="models", max_keep=5):
        self.models_dir = models_dir
        self.max_keep = max_keep
        os.makedirs(self.models_dir, exist_ok=True)
        
    def generate_save_path(self, tag_name, model_type):
        """ EX: models/TEMP_BOILER_OUT_LSTM_20240320_153022.onnx """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{tag_name}_{model_type}_{timestamp}.onnx"
        return os.path.join(self.models_dir, filename)
        
    def cleanup_old_models(self, tag_name):
        """ 지정된 태그의 과거 모델 파일들을 검색하여 갯수 제한(max_keep) 유지 """
        pattern = os.path.join(self.models_dir, f"{tag_name}_*.onnx")
        files = glob.glob(pattern)
        
        # 이름의 마지막 부분(timestamp) 기준 오름차순 정렬
        files.sort()
        
        # 파일이 max_keep 개수를 초과하면 오래된 것부터 삭제
        if len(files) > self.max_keep:
            files_to_delete = files[:-self.max_keep]
            for f in files_to_delete:
                try:
                    os.remove(f)
                    print(f"[Cleanup] Removed old model: {f}")
                except Exception as e:
                    print(f"[Cleanup Failed] {f}: {e}")
                    
    def get_latest_model_path(self, tag_name):
        """ 해당 태그명에 대해 가장 최근 생성된 ONNX 모델 로드 """
        pattern = os.path.join(self.models_dir, f"{tag_name}_*.onnx")
        files = glob.glob(pattern)
        if not files:
            return None
            
        files.sort()
        return files[-1] # 가장 최신 파일 반환
