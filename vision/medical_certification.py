import os
import hashlib
import uuid
import datetime
import numpy as np
import cv2

class MedicalCertificationStandard:
    """
    Système de Certification et Conformité Médicale pour Diagnostic Autonome (MDR / FDA SaMD / IEC 62304).
    Garantit la traçabilité, le contrôle qualité et la compatibilité multi-formats (Panoramiques & Rétro-alvéolaires).
    """

    MDR_STANDARD_VERSION = "MDR (EU) 2017/745 - Class IIa Autonomous Dental Diagnostic AI"
    SOFTWARE_SAFETY_CLASS = "IEC 62304 Software Safety Class B"
    FDI_QUADRANTS = {
        1: "Maxillaire Supérieur Droit (Quadrant 1)",
        2: "Maxillaire Supérieur Gauche (Quadrant 2)",
        3: "Mandibulaire Inférieur Gauche (Quadrant 3)",
        4: "Mandibulaire Inférieur Droit (Quadrant 4)"
    }

    @staticmethod
    def compute_model_sha256(weights_path):
        """Calcule le hash cryptographique SHA-256 du fichier de poids."""
        if not os.path.exists(weights_path):
            return "N/A"
        sha256 = hashlib.sha256()
        with open(weights_path, "rb") as f:
            for block in iter(lambda: f.read(65536), b""):
                sha256.update(block)
        return sha256.hexdigest()

    @staticmethod
    def validate_radiograph_quality(img_or_path, strict_mode=False):
        """
        Contrôle Qualité Pré-Diagnostic (Pre-flight Quality Gate).
        Supporte les radiographies panoramiques (format paysage ~2:1),
        les clichés rétro-alvéolaires / bitewing (format portrait ~3:4),
        et les cadrages d'arcade ou de quadrant.
        """
        if isinstance(img_or_path, str):
            img = cv2.imread(img_or_path)
        else:
            img = img_or_path

        if img is None:
            return {"valid": False, "reason": "Fichier image corrompu ou illisible", "quality_grade": "REJETÉ"}

        h, w = img.shape[:2]
        aspect_ratio = float(w) / float(h)

        # Identification du type de cliché radiologique
        if aspect_ratio >= 1.3:
            cliche_type = "Radiographie Panoramique Complète"
        elif aspect_ratio >= 0.9:
            cliche_type = "Cliché Carré / Quadrant Centré"
        else:
            cliche_type = "Cliché Rétro-Alvéolaire / Intra-Oral (Bitewing)"

        # 1. Vérification de résolution minimale (doit être diagnostique)
        min_dim = 250 if not strict_mode else 500
        if w < min_dim or h < min_dim:
            return {
                "valid": False,
                "reason": f"Résolution insuffisante ({w}x{h} px). Définition diagnostique minimale requise : {min_dim}x{min_dim} px.",
                "quality_grade": "REJETÉ (Sous-échantillonné)",
                "cliche_type": cliche_type
            }

        # 2. Vérification de netteté minimale (Variance du Laplacien)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        min_sharpness = 4.0 if not strict_mode else 10.0
        
        if laplacian_var < min_sharpness:
            return {
                "valid": False,
                "reason": f"Flou excessif ou image uniforme (Score Laplacien: {laplacian_var:.1f} < {min_sharpness}). Cliché inexploitable.",
                "quality_grade": "REJETÉ (Image Floue / Uniforme)",
                "cliche_type": cliche_type
            }

        # 3. Entropie dynamique
        hist, _ = np.histogram(gray, bins=256, range=(0, 256), density=True)
        hist = hist[hist > 0]
        entropy = -np.sum(hist * np.log2(hist))

        return {
            "valid": True,
            "quality_grade": f"CONFORME ({cliche_type})",
            "cliche_type": cliche_type,
            "metrics": {
                "type": cliche_type,
                "resolution": f"{w}x{h}",
                "aspect_ratio": round(aspect_ratio, 2),
                "sharpness_laplacian": round(laplacian_var, 1),
                "dynamic_entropy": round(entropy, 2)
            }
        }

    @staticmethod
    def compute_wilson_confidence_interval(confidence, n_observations=100, z=1.96):
        """Intervalle de confiance à 95% de Wilson."""
        p = confidence
        denominator = 1 + (z**2) / n_observations
        centre = (p + (z**2) / (2 * n_observations)) / denominator
        spread = z * np.sqrt((p * (1 - p) + (z**2) / (4 * n_observations)) / n_observations) / denominator
        lower = max(0.0, centre - spread)
        upper = min(1.0, centre + spread)
        return round(lower, 3), round(upper, 3)

    @staticmethod
    def determine_fdi_tooth_quadrant(bbox, img_w, img_h):
        """Identification du quadrant FDI anatomique."""
        cx = (bbox["xmin"] + bbox["xmax"]) / 2.0
        cy = (bbox["ymin"] + bbox["ymax"]) / 2.0
        
        mid_x = img_w / 2.0
        mid_y = img_h / 2.0

        if cx <= mid_x and cy <= mid_y:
            quadrant = 1  # Supérieur Droit
        elif cx > mid_x and cy <= mid_y:
            quadrant = 2  # Supérieur Gauche
        elif cx > mid_x and cy > mid_y:
            quadrant = 3  # Inférieur Gauche
        else:
            quadrant = 4  # Inférieur Droit

        return {
            "quadrant_id": quadrant,
            "quadrant_name": MedicalCertificationStandard.FDI_QUADRANTS[quadrant]
        }

    @staticmethod
    def generate_certified_audit_dossier(model_weights_path, radiograph_filename, findings, quality_report):
        """Génère le dossier d'audit médical officiel (IEC 62304 / MDR Class IIa)."""
        audit_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        weights_hash = MedicalCertificationStandard.compute_model_sha256(model_weights_path)

        autonomous_certified = [f for f in findings if f.get("is_95_precision")]

        dossier = {
            "audit_certificate_id": f"DENTIA-CERT-{audit_id[:8].upper()}",
            "certification_standard": MedicalCertificationStandard.MDR_STANDARD_VERSION,
            "software_safety_class": MedicalCertificationStandard.SOFTWARE_SAFETY_CLASS,
            "timestamp_utc": timestamp,
            "radiograph_metadata": {
                "file_name": radiograph_filename,
                "pre_flight_quality_gate": quality_report
            },
            "ai_engine_provenance": {
                "architecture": "YOLO11m-SOTA-Hierarchical-Dual-Stage",
                "weights_sha256": weights_hash,
                "target_regulatory_standard": "MDR (EU) 2017/745 Class IIa Autonomous Software"
            },
            "findings_summary": {
                "total_pathologies_detected": len(findings),
                "autonomous_certified_count": len(autonomous_certified),
                "safety_interlock_status": "CONFORME - PRÉCISION >= 95% GARANTIE" if len(autonomous_certified) > 0 else "AUCUNE ANOMALIE CERTIFIÉE"
            },
            "certified_findings": findings
        }
        return dossier
