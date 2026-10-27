import time
import torch
from ultralytics import YOLO

def benchmark_inference():
    models = {
        "YOLOv8n": "yolov8n.pt",
        "YOLOv8s": "yolov8s.pt",
        "YOLO11n": "yolo11n.pt",
        "YOLO11s": "yolo11s.pt",
        "YOLO11m": "yolo11m.pt"
    }
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Benchmarking on device: {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")
    print("-" * 75)
    print(f"{'Model':<12} | {'Params (M)':<12} | {'Weights (MB)':<14} | {'Latency (ms)':<14} | {'FPS':<8}")
    print("-" * 75)
    
    # Warmup image (dummy tensor of size 1x3x640x640)
    dummy_input = torch.randn(1, 3, 640, 640).to(device)
    
    results = {}
    
    for name, weight in models.items():
        try:
            m = YOLO(weight)
            m.to(device)
            
            # Count params
            params = sum(p.numel() for p in m.model.parameters()) / 1e6
            
            # Warm up
            for _ in range(10):
                _ = m.model(dummy_input)
                
            # Measure time
            torch.cuda.synchronize() if device == "cuda" else None
            start = time.perf_counter()
            iters = 50
            for _ in range(iters):
                _ = m.model(dummy_input)
            torch.cuda.synchronize() if device == "cuda" else None
            end = time.perf_counter()
            
            avg_time_ms = ((end - start) / iters) * 1000.0
            fps = 1000.0 / avg_time_ms
            
            import os
            mb_size = os.path.getsize(weight) / (1024 * 1024) if os.path.exists(weight) else 0.0
            
            print(f"{name:<12} | {params:<12.2f} | {mb_size:<14.1f} | {avg_time_ms:<14.2f} | {fps:<8.1f}")
            results[name] = {
                "params_m": params,
                "size_mb": mb_size,
                "latency_ms": avg_time_ms,
                "fps": fps
            }
        except Exception as e:
            print(f"Error testing {name}: {e}")
            
    print("-" * 75)
    return results

if __name__ == "__main__":
    benchmark_inference()
