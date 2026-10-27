import torch
from ultralytics import YOLO

def train():
    device = 0 if torch.cuda.is_available() else "cpu"
    print(f"Starting fine-tuning test on device: {device}")
    
    # Load model
    model = YOLO("yolo11s.pt")
    
    # Train test (3 epochs to verify convergence, batch memory, and metrics)
    results = model.train(
        data="dentex_yolo/data.yaml",
        epochs=3,
        imgsz=640,
        batch=8,
        device=device,
        workers=2,
        project="dentiai_experiments",
        name="yolo11s_dentex_test",
        exist_ok=True
    )
    print("Test training completed successfully!")
    return results

if __name__ == "__main__":
    train()
