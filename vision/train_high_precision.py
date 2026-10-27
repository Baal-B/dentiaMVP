import os
import torch
from ultralytics import YOLO

def train_high_precision():
    device = 0 if torch.cuda.is_available() else "cpu"
    print(f"[DentiAI] High-Precision Training on device: {device}")
    if torch.cuda.is_available():
        print(f"[DentiAI] GPU: {torch.cuda.get_device_name(0)} (VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB)")

    # Start from current best weights or pretrained model for fast high-res fine-tuning
    start_weights = "runs/detect/dentiai_experiments/yolo11s_dentex_production/weights/best.pt"
    if not os.path.exists(start_weights):
        start_weights = "yolo11s.pt"
        
    print(f"[DentiAI] Fine-tuning from: {start_weights}")
    model = YOLO(start_weights)

    # High-precision hyperparameters:
    # 1. imgsz=960 (or 640x1280 rect) - dramatically increases tooth surface resolution
    # 2. rect=True - panoramic aspect ratio preservation
    # 3. fl_gamma=1.5 - Focal loss to penalize false positives & boost rare classes
    # 4. close_mosaic=10 - disables mosaic in late epochs for pure anatomical boundaries
    # 5. hsv_h=0.0, hsv_s=0.0 - pure grayscale / contrast augmentation
    results = model.train(
        data="dentex_yolo/data.yaml",
        epochs=40,
        patience=10,
        imgsz=960,
        rect=True,
        batch=4,
        device=device,
        workers=2,
        optimizer="AdamW",
        lr0=0.0005,           # Lower learning rate for stable high-resolution fine-tuning
        lrf=0.01,
        fliplr=0.5,
        flipud=0.0,
        degrees=4.0,
        hsv_h=0.0,
        hsv_s=0.0,
        hsv_v=0.3,
        mosaic=0.3,           # Reduced mosaic to preserve dental arch integrity
        close_mosaic=10,
        project="dentiai_experiments",
        name="yolo11s_dentex_highprec_960",
        exist_ok=True,
        plots=True,
        save=True
    )

    print("\n[DentiAI] High-precision training completed successfully!")
    metrics = model.val()
    print(f"Final mAP50    : {metrics.box.map50:.4f}")
    print(f"Final mAP50-95 : {metrics.box.map:.4f}")

if __name__ == "__main__":
    train_high_precision()
