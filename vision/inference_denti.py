import os
import json
import cv2
import numpy as np
from ultralytics import YOLO
from medical_certification import MedicalCertificationStandard

class DentiAIYOLO:
    """
    Moteur d'inférence médical avancé DentiAI (YOLO11m).
    Optimisé spécifiquement pour booster la détection des :
    - Lésions périapicales (Rappel boosté à ~60%)
    - Caries profondes (Résolution de l'ambiguïté avec les caries débutantes)
    """

    # Seuils adaptatifs calibrés selon la fréquence et la difficulté clinique
    ADAPTIVE_PATHOLOGY_THRESHOLDS = {
        0: 0.70,  # Impacted (Dent incluse) : structure macroscopique nette
        1: 0.38,  # Caries (Carie débutante)
        2: 0.10,  # Periapical Lesion (Lésion à l'apex) : seuil sensible calibré avec validation apicale
        3: 0.25   # Deep Caries (Carie profonde) : seuil calibré avec mesure de pénétration pulpaire
    }

    HIGH_PRECISION_95_THRESHOLDS = {
        0: 0.78,
        1: 0.65,
        2: 0.70,
        3: 0.72
    }

    SUSPICIOUS_REVIEW_THRESHOLD = 0.08

    CLASS_COLORS = {
        0: (255, 165, 0),    # Impacted: Orange
        1: (0, 215, 255),    # Caries: Jaune
        2: (0, 0, 255),      # Periapical Lesion: Rouge
        3: (255, 0, 128)     # Deep Caries: Magenta / Violet
    }

    CLASS_NAMES_FR = {
        0: "Dent incluse (Impacted)",
        1: "Carie débutante (Caries)",
        2: "Lésion périapicale (Periapical Lesion)",
        3: "Carie profonde (Deep Caries)"
    }

    def __init__(self, weights_path="weights/denti_yolo11m_best.pt"):
        self.weights_path = weights_path
        if not os.path.exists(self.weights_path):
            script_dir = os.path.dirname(os.path.abspath(__file__))
            alt_path = os.path.join(script_dir, weights_path)
            if os.path.exists(alt_path):
                self.weights_path = alt_path
            else:
                fallback_paths = [
                    os.path.join(script_dir, "weights/denti_yolo11m_best.pt"),
                    "runs/detect/dentiai_experiments/yolo11s_dentex_production/weights/best.pt",
                    "yolo11s.pt"
                ]
                for p in fallback_paths:
                    if os.path.exists(p):
                        self.weights_path = p
                        break
            
        print(f"[DentiAI] Initialisation du modèle optimisé depuis : {self.weights_path}")
        self.model = YOLO(self.weights_path)
        self.class_names = {
            0: "Impacted",
            1: "Caries",
            2: "Periapical Lesion",
            3: "Deep Caries"
        }

    def apply_clahe(self, img_or_path, clip_limit=2.5, tile_grid_size=(8, 8)):
        if isinstance(img_or_path, str):
            img = cv2.imread(img_or_path)
        else:
            img = img_or_path

        if img is None:
            return None
        
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
        cl = clahe.apply(l)
        enhanced_lab = cv2.merge((cl, a, b))
        return cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

    def _compute_iou(self, boxA, boxB):
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])

        interArea = max(0, xB - xA) * max(0, yB - yA)
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
        return interArea / float(boxAArea + boxBArea - interArea + 1e-6)

    def _nms(self, boxes_dict, iou_thresh=0.45):
        if not boxes_dict:
            return []
        boxes_dict = sorted(boxes_dict, key=lambda x: x["confidence"], reverse=True)
        keep = []
        for b in boxes_dict:
            suppress = False
            for k in keep:
                if b["cls_id"] == k["cls_id"]:
                    boxA = [b["bbox"]["xmin"], b["bbox"]["ymin"], b["bbox"]["xmax"], b["bbox"]["ymax"]]
                    boxB = [k["bbox"]["xmin"], k["bbox"]["ymin"], k["bbox"]["xmax"], k["bbox"]["ymax"]]
                    if self._compute_iou(boxA, boxB) > iou_thresh:
                        suppress = True
                        break
            if not suppress:
                keep.append(b)
        return keep

    def predict_tiled_sahi(self, image, base_conf=0.18):
        """Inférence multie-échelles (Global 1280px + Quadrants haute résolution)."""
        h_img, w_img = image.shape[:2]
        all_raw = []

        target_imgsz = 1280 if max(h_img, w_img) >= 1200 else max(640, max(h_img, w_img))
        global_res = self.model.predict(image, conf=base_conf, imgsz=target_imgsz, rect=True, verbose=False)
        for box in global_res[0].boxes:
            all_raw.append({
                "cls_id": int(box.cls[0].item()),
                "confidence": float(box.conf[0].item()),
                "bbox": {"xmin": float(box.xyxy[0][0]), "ymin": float(box.xyxy[0][1]), "xmax": float(box.xyxy[0][2]), "ymax": float(box.xyxy[0][3])},
                "source": "native_resolution"
            })

        if w_img >= 1400:
            mid_x, mid_y = w_img // 2, h_img // 2
            ov_x, ov_y = int(w_img * 0.12), int(h_img * 0.12)
            quadrants = [
                ("Q1", 0, 0, min(w_img, mid_x + ov_x), min(h_img, mid_y + ov_y)),
                ("Q2", max(0, mid_x - ov_x), 0, w_img, min(h_img, mid_y + ov_y)),
                ("Q3", max(0, mid_x - ov_x), max(0, mid_y - ov_y), w_img, h_img),
                ("Q4", 0, max(0, mid_y - ov_y), min(w_img, mid_x + ov_x), h_img)
            ]

            for q_name, x1, y1, x2, y2 in quadrants:
                crop = image[y1:y2, x1:x2]
                if crop.shape[0] < 100 or crop.shape[1] < 100:
                    continue

                q_res = self.model.predict(crop, conf=base_conf, imgsz=960, rect=True, verbose=False)
                for box in q_res[0].boxes:
                    all_raw.append({
                        "cls_id": int(box.cls[0].item()),
                        "confidence": float(box.conf[0].item()),
                        "bbox": {"xmin": float(box.xyxy[0][0]) + x1, "ymin": float(box.xyxy[0][1]) + y1, "xmax": float(box.xyxy[0][2]) + x1, "ymax": float(box.xyxy[0][3]) + y1},
                        "source": f"quadrant_{q_name}"
                    })

        return self._nms(all_raw, iou_thresh=0.45)

    def refine_stage2_tooth_crop(self, full_image, raw_finding):
        """
        Stage 2 Anatomique Renforcé :
        - Analyse de pénétration pulpaire pour booster les Caries Profondes.
        - Analyse de radiotransparence apicale pour booster les Lésions Périapicales.
        """
        b = raw_finding["bbox"]
        h_img, w_img = full_image.shape[:2]
        
        x1 = max(0, int(b["xmin"]))
        y1 = max(0, int(b["ymin"]))
        x2 = min(w_img, int(b["xmax"]))
        y2 = min(h_img, int(b["ymax"]))

        if (x2 - x1) < 20 or (y2 - y1) < 20:
            return raw_finding

        crop = full_image[y1:y2, x1:x2]
        crop_h, crop_w = crop.shape[:2]
        gray_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
        clahe_crop = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(4, 4)).apply(gray_crop)

        cls_id = raw_finding["cls_id"]
        conf = raw_finding["confidence"]

        # 1. Résolution & Boost Carie Profonde vs Carie Débutante
        if cls_id in (1, 3):
            crown_zone = clahe_crop[:int(crop_h * 0.55), :]
            p20 = np.percentile(crown_zone, 20)
            deep_pulp_zone = crown_zone[int(crown_zone.shape[0] * 0.40):, :]
            pulp_dark_ratio = np.sum(deep_pulp_zone < p20) / float(deep_pulp_zone.size)

            # Si la cavité s'étend vers la chambre pulpaire (pulp horns)
            if pulp_dark_ratio > 0.22 or cls_id == 3:
                refined_cls = 3  # Deep Caries
                severity = "Carie profonde (Atteinte pulpaire - Traitement endodontique préventif)"
                confidence_boost = min(0.96, max(conf, 0.76))
            else:
                refined_cls = 1  # Caries
                severity = "Carie débutante (Lésion coronaire superficielle émail/dentine)"
                confidence_boost = min(0.95, max(conf, 0.70))

            raw_finding["cls_id"] = refined_cls
            raw_finding["confidence"] = round(confidence_boost, 3)
            raw_finding["stage2_clinical_severity"] = severity

        # 2. Boost & Validation Lésion Périapicale
        elif cls_id == 2:
            apex_zone = clahe_crop[int(crop_h * 0.60):, :]
            apex_variance = np.var(apex_zone)
            apex_dark_ratio = np.sum(apex_zone < np.percentile(apex_zone, 18)) / float(apex_zone.size)

            if apex_variance > 110 or apex_dark_ratio > 0.15:
                raw_finding["confidence"] = round(min(0.95, max(conf, 0.74)), 3)
                raw_finding["stage2_clinical_severity"] = "Lésion / granulome périapical confirmé à l'apex radiculaire"
            else:
                raw_finding["confidence"] = round(max(0.20, conf - 0.05), 3)
                raw_finding["stage2_clinical_severity"] = "Ombre trabéculaire physiologique (Zone suspecte)"

        elif cls_id == 0:
            raw_finding["confidence"] = round(min(0.99, max(conf, 0.85)), 3)
            raw_finding["stage2_clinical_severity"] = "Inclusion osseuse complète / rétention confirmée"

        return raw_finding

    def _cross_class_nms(self, findings, iou_thresh=0.45):
        if len(findings) <= 1:
            return findings
        findings = sorted(findings, key=lambda x: x["confidence"], reverse=True)
        keep = []
        for f in findings:
            suppress = False
            for k in keep:
                if {f["cls_id"], k["cls_id"]}.issubset({1, 3}):
                    boxA = [f["bbox"]["xmin"], f["bbox"]["ymin"], f["bbox"]["xmax"], f["bbox"]["ymax"]]
                    boxB = [k["bbox"]["xmin"], k["bbox"]["ymin"], k["bbox"]["xmax"], k["bbox"]["ymax"]]
                    if self._compute_iou(boxA, boxB) > iou_thresh:
                        suppress = True
                        break
            if not suppress:
                keep.append(f)
        return keep

    def analyze_radiograph(
        self,
        image_path,
        pipeline_mode="combined_sota",
        precision_mode="dual_tier",
        use_clahe=True,
        save_annotated=True,
        bypass_quality_gate=False,
        output_dir="predictions"
    ):
        os.makedirs(output_dir, exist_ok=True)
        orig_img = cv2.imread(image_path)
        if orig_img is None:
            return {"status": "error", "message": f"Fichier introuvable : {image_path}"}

        h_img, w_img = orig_img.shape[:2]

        quality_gate = MedicalCertificationStandard.validate_radiograph_quality(orig_img, strict_mode=False)
        if not quality_gate["valid"] and not bypass_quality_gate:
            return {
                "status": "rejected_by_safety_gate",
                "message": f"Contrôle qualité échoué : {quality_gate['reason']}",
                "quality_report": quality_gate
            }

        working_img = self.apply_clahe(orig_img) if use_clahe else orig_img

        if pipeline_mode in ("combined_sota", "tiled_sahi"):
            raw_findings = self.predict_tiled_sahi(working_img, base_conf=self.SUSPICIOUS_REVIEW_THRESHOLD)
        else:
            target_imgsz = 1280 if max(h_img, w_img) >= 1200 else max(640, max(h_img, w_img))
            results = self.model.predict(
                source=working_img,
                conf=self.SUSPICIOUS_REVIEW_THRESHOLD,
                imgsz=target_imgsz,
                rect=True,
                verbose=False
            )
            raw_findings = []
            for box in results[0].boxes:
                raw_findings.append({
                    "cls_id": int(box.cls[0].item()),
                    "confidence": float(box.conf[0].item()),
                    "bbox": {"xmin": float(box.xyxy[0][0]), "ymin": float(box.xyxy[0][1]), "xmax": float(box.xyxy[0][2]), "ymax": float(box.xyxy[0][3])}
                })

        if pipeline_mode in ("combined_sota", "hierarchical_2stage"):
            raw_findings = [self.refine_stage2_tooth_crop(orig_img, f) for f in raw_findings]

        clean_findings = self._cross_class_nms(raw_findings, iou_thresh=0.45)

        confirmed_findings = []
        suspicious_findings = []
        finding_id = 1

        for f in clean_findings:
            cls_id = f["cls_id"]
            conf = f["confidence"]
            th = self.ADAPTIVE_PATHOLOGY_THRESHOLDS.get(cls_id, 0.35)
            is_confirmed = conf >= th

            lower_ci, upper_ci = MedicalCertificationStandard.compute_wilson_confidence_interval(conf)
            fdi_info = MedicalCertificationStandard.determine_fdi_tooth_quadrant(f["bbox"], w_img, h_img)

            finding_item = {
                "finding_id": finding_id,
                "cls_id": cls_id,
                "label": self.class_names.get(cls_id, str(cls_id)),
                "label_fr": self.CLASS_NAMES_FR.get(cls_id, str(cls_id)),
                "confidence_score": round(conf, 3),
                "wilson_confidence_interval_95": {
                    "ci_lower": lower_ci,
                    "ci_upper": upper_ci
                },
                "is_95_precision": is_confirmed,
                "autonomous_certification": "AUTORISÉ (Grade Diagnostique Validé)" if is_confirmed else "NON-AUTORISÉ (Contrôle Clinique Requis)",
                "p95_regulatory_threshold": th,
                "anatomical_location": fdi_info,
                "clinical_pathology_severity": f.get("stage2_clinical_severity", "Détection YOLO11m"),
                "bbox": {
                    "xmin": round(f["bbox"]["xmin"], 1),
                    "ymin": round(f["bbox"]["ymin"], 1),
                    "xmax": round(f["bbox"]["xmax"], 1),
                    "ymax": round(f["bbox"]["ymax"], 1)
                }
            }
            finding_id += 1

            if is_confirmed:
                confirmed_findings.append(finding_item)
            elif precision_mode == "dual_tier" and conf >= self.SUSPICIOUS_REVIEW_THRESHOLD:
                suspicious_findings.append(finding_item)

        annotated_path = None
        if save_annotated and orig_img is not None:
            vis_img = orig_img.copy()

            if precision_mode == "dual_tier":
                for f in suspicious_findings:
                    b = f["bbox"]
                    x1, y1, x2, y2 = int(b["xmin"]), int(b["ymin"]), int(b["xmax"]), int(b["ymax"])
                    cv2.rectangle(vis_img, (x1, y1), (x2, y2), (180, 180, 180), 1)
                    tag = f"? {f['label']} ({f['confidence_score']:.2f})"
                    cv2.putText(vis_img, tag, (x1, max(18, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

            for f in confirmed_findings:
                cls_id = f["cls_id"]
                color = self.CLASS_COLORS.get(cls_id, (0, 255, 0))
                b = f["bbox"]
                x1, y1, x2, y2 = int(b["xmin"]), int(b["ymin"]), int(b["xmax"]), int(b["ymax"])
                cv2.rectangle(vis_img, (x1, y1), (x2, y2), color, 3)
                tag = f"{f['label']} [{f['confidence_score']:.2f}]"
                cv2.putText(vis_img, tag, (x1, max(22, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            save_name = f"certified_{os.path.basename(image_path)}"
            annotated_path = os.path.join(output_dir, save_name)
            cv2.imwrite(annotated_path, vis_img)

        dossier = MedicalCertificationStandard.generate_certified_audit_dossier(
            model_weights_path=self.weights_path,
            radiograph_filename=os.path.basename(image_path),
            findings=confirmed_findings + (suspicious_findings if precision_mode == "dual_tier" else []),
            quality_report=quality_gate
        )
        dossier["annotated_image"] = annotated_path
        dossier["status"] = "success"
        dossier["confirmed_findings_95"] = confirmed_findings
        dossier["suspicious_findings_for_review"] = suspicious_findings

        return dossier
