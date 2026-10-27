# DentIA - Computer Vision Module

Module de détection automatique des pathologies dentaires sur radiographies panoramiques basé sur **YOLO11**.

## Pathologies Détectées
| Classe | Pathologie | Seuil Haute Précision (>=95%) | Couleur Annotation |
|---|---|---|---|
| `0` | **Impacted** (Dent incluse) | 0.82 | Orange |
| `1` | **Caries** (Carie) | 0.84 | Jaune |
| `2` | **Periapical Lesion** (Lésion périapicale) | 0.78 | Rouge |
| `3` | **Deep Caries** (Carie profonde) | 0.83 | Magenta |

*Un mode révision / zone suspecte (`SUSPICIOUS_REVIEW_THRESHOLD = 0.35`) permet également de signaler aux praticiens les zones d'attention sans faux diagnostic définitif.*

---

## Installation & Setup
```bash
cd vision
python -m venv .venv
.venv\Scripts\activate           # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

---

## Inférence & Diagnostic Rapide
```python
from inference_denti import DentiAIYOLO

# Initialisation (charge automatiquement le modèle calibré weights/denti_yolo11m_best.pt)
detector = DentiAIYOLO()

# Analyse d'une radiographie panoramique
results = detector.predict("path/to/xray.png", output_dir="predictions")
print(results)
```

Ou en ligne de commande :
```bash
python inference_denti.py --image path/to/radiographie.png
```

---

## Organisation des Fichiers
| Fichier | Rôle |
|---|---|
| `inference_denti.py` | Moteur d'inférence avec pré-traitement CLAHE et seuillage haute précision |
| `weights/denti_yolo11m_best.pt` | Poids du modèle entraîné (YOLO11m calibré) |
| `prepare_yolo_dataset.py` | Préparation et conversion du dataset DENTEX au format YOLO |
| `train_high_precision.py` | Entraînement optimisé avec hyperparamètres haute précision |
| `train_full_yolo11.py` | Pipeline d'entraînement complet YOLO11 |
| `train_dentex.py` | Script de base fine-tuning DENTEX |
| `benchmark_models.py` | Benchmark comparatif des architectures YOLO (n, s, m) |
| `eval_yolo11m_precision.py` | Évaluation des métriques de précision / rappel par classe |
| `eval_precision_sweep.py` | Balayage des seuils de confiance pour garantir >= 95% de précision |
| `DentiAI_Kaggle_Trainer.ipynb` | Notebook d'entraînement cloud (Kaggle GPU T4 / P100) |
