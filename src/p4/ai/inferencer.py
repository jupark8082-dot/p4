import onnxruntime as ort
import numpy as np

class ONNXInferencer:
    """
    FastAPI 서버 내부에서 백그라운드로 주기적으로 작동하여,
    가장 최신화된 ONNX 파일을 메모리로 로드하고 초고속 CPU 추론을 수행.
    """
    def __init__(self):
        self.sessions = {} # tag_name 별 세션 캐싱
        self.model_paths = {} # tag_name 별 현재 로드된 모델 경로
        
    def load_model(self, tag_name, model_path):
        """ 모델 경로가 변경되었거나 최초 로드 시 InferenceSession 생성 """
        if tag_name not in self.model_paths or self.model_paths[tag_name] != model_path:
            print(f"[Inferencer] Loading ONNX model for {tag_name}...")
            # CPU 전용 추론 실행 (GPU 부재 대응)
            providers = ['CPUExecutionProvider']
            session = ort.InferenceSession(model_path, providers=providers)
            self.sessions[tag_name] = session
            self.model_paths[tag_name] = model_path
            
    def predict(self, tag_name, model_path, input_tensor, scaler=None):
        """
        input_tensor: numpy array shape (1, Sequence Length, Features)
        scaler: 데이터 전처리에 사용했던 scikit-learn scaler 객체(주어질 경우)
        """
        self.load_model(tag_name, model_path)
        session = self.sessions.get(tag_name)
        if session is None:
            raise ValueError(f"Model for {tag_name} not properly loaded.")
            
        input_name = session.get_inputs()[0].name
        output_name = session.get_outputs()[0].name
        
        # 스케일링 전처리
        scaled_input = input_tensor
        if scaler is not None:
             # (1, Seq, Feat) -> (Seq, Feat) 스케일링 후 복구
             shape = input_tensor.shape
             flat = input_tensor.reshape(-1, shape[-1])
             scaled_flat = scaler.transform(flat)
             scaled_input = scaled_flat.reshape(shape)
             
        # float32 캐스팅
        scaled_input = scaled_input.astype(np.float32)

        # ONNX Run
        outputs = session.run([output_name], {input_name: scaled_input})
        
        # 결과값 역산 (역정규화)
        # scaler.inverse_transform 지원 방식에 따라 복원 로직 추가 필요
        # 단변량이라면 단순 scalar 복원
        result = outputs[0][0] 
        
        return float(result)
