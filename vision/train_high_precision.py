import os
import torch
from ultralytics import YOLO

def train_high_precision():
    """
    Entraînement / Fine-tuning Haute Précision (>= 95%) pour DentiAI.
    Optimisé pour GPU local (RTX 2050 4GB) ou GPU Cloud (Kaggle / Colab).
    """
    device = 0 if torch.cuda.is_available() else "cpu"
    print(f"[DentiAI] Fine-tuning Haute Précision sur : {device}")
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"[DentiAI] GPU : {gpu_name} (VRAM : {vram_gb:.2f} GB)")

    # Démarrer à partir du meilleur modèle YOLO11m calibré
    start_weights = "weights/denti_yolo11m_best.pt"
    if not os.path.exists(start_weights):
        start_weights = "runs/detect/dentiai_experiments/yolo11s_dentex_production/weights/best.pt"
    if not os.path.exists(start_weights):
        start_weights = "yolo11s.pt"
        
    print(f"[DentiAI] Initialisation des poids depuis : {start_weights}")
    model = YOLO(start_weights)

    # Hyperparamètres orientés Haute Précision médicale :
    # 1. cls=1.5 (Poids x3 sur la classification pour éliminer les faux positifs)
    # 2. cls_pw=1.2 (Pondération positive pour équilibrer la classe rare Lésion périapicale)
    # 3. rect=True (Préservation de l'aspect ratio 2:1 panoramique sans déformation)
    # 4. hsv_h=0, hsv_s=0 (Invariance radiologique niveaux de gris)
    # 5. close_mosaic=10 (Suppression du mosaic en fin d'entraînement pour netteté anatomique)
    results = model.train(
        data="dentex_yolo/data.yaml",
        epochs=30,
        patience=8,
        imgsz=640,
        rect=True,
        batch=4,
        device=device,
        workers=2,
        optimizer="AdamW",
        lr0=0.0003,            # Taux d'apprentissage modéré pour fine-tuning fin
        lrf=0.01,
        cls=1.5,               # Focalisation sur la pureté de classe
        cls_pw=1.2,            # Boost des classes minoritaires (périapicales)
        fliplr=0.5,            # Symétrie gauche/droite de l'arcade dentaire
        flipud=0.0,
        degrees=3.0,
        hsv_h=0.0,
        hsv_s=0.0,
        hsv_v=0.35,
        mosaic=0.2,            # Mosaic très réduit pour préserver l'anatomie dentaire
        close_mosaic=10,
        project="dentiai_experiments",
        name="yolo11_dentex_highprec_95",
        exist_ok=True,
        plots=True,
        save=True
    )

    print("\n[DentiAI] Entraînement haute précision terminé avec succès !")
    metrics = model.val()
    print(f"mAP@50    : {metrics.box.map50:.4f}")
    print(f"mAP@50-95 : {metrics.box.map:.4f}")

if __name__ == "__main__":
    train_high_precision()
