import os
import torch
from ultralytics import YOLO

def train_yolo11():
    # Detect GPU
    device = 0 if torch.cuda.is_available() else "cpu"
    print(f"[DentiAI] Entraînement de YOLO11 sur le device : {device}")
    if torch.cuda.is_available():
        print(f"[DentiAI] GPU : {torch.cuda.get_device_name(0)}")

    # Initialisation du modèle YOLO11 Small pré-entraîné
    model = YOLO("yolo11s.pt")

    # Hyperparamètres optimisés pour les radiographies panoramiques (DENTEX)
    results = model.train(
        data="dentex_yolo/data.yaml",
        epochs=60,               # Nombre d'époques suffisant pour une convergence optimale
        patience=12,             # Early stopping pour éviter l'overfitting
        imgsz=640,               # Résolution adaptée à la VRAM de 4 Go
        batch=8,                 # Taille de lot stable sans risque d'OOM
        device=device,
        workers=2,
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,
        # Augmentations adaptées à la radiologie dentaire
        fliplr=0.5,              # Symétrie gauche/droite pertinente pour les mâchoires
        flipud=0.0,              # Pas d'inversion haut/bas (le maxillaire et la mandibule ont un sens)
        degrees=5.0,             # Légère rotation
        project="dentiai_experiments",
        name="yolo11s_dentex_production",
        exist_ok=True,
        plots=True,
        save=True
    )

    print("\n[DentiAI] Entraînement terminé avec succès !")
    print("Meilleurs poids sauvegardés dans : runs/detect/dentiai_experiments/yolo11s_dentex_production/weights/best.pt")
    
    # Validation finale
    metrics = model.val()
    print(f"mAP50-95 final : {metrics.box.map:.4f}")
    print(f"mAP50 final    : {metrics.box.map50:.4f}")

if __name__ == "__main__":
    train_yolo11()
