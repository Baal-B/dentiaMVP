"""
DENTEX assistive-diagnosis API (FastAPI).

Decision-support only: every output must be reviewed by a dentist.
Run:  uvicorn app:app --host 0.0.0.0 --port 8000
"""
import json
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from ultralytics import YOLO

BASE = Path(__file__).parent
MODEL_DIR = Path(os.getenv("MODEL_DIR", BASE / "models"))
IMGSZ = int(os.getenv("IMGSZ", "1280"))
DEVICE = os.getenv("DEVICE", "cpu")                      # "0" if you have an NVIDIA GPU
MAX_BYTES = int(os.getenv("MAX_UPLOAD_MB", "25")) * 1024 * 1024
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")]
CARIES_FAMILY = ("Caries", "Deep Caries")
DISCLAIMER = ("Decision-support prototype, not a medical device. Findings are suggestions "
              "that must be reviewed and confirmed by a qualified dentist.")

state: dict = {}
lock = threading.Lock()   # one inference at a time (YOLO objects are not thread-safe)


@asynccontextmanager
async def lifespan(app: FastAPI):
    disease_path = MODEL_DIR / "disease_best.pt"
    if not disease_path.exists():
        raise RuntimeError(f"Missing {disease_path}. Put your weights in the models/ folder.")
    state["disease"] = YOLO(str(disease_path))
    tooth_path = MODEL_DIR / "tooth_best.pt"
    state["tooth"] = YOLO(str(tooth_path)) if tooth_path.exists() else None
    cfg_path = MODEL_DIR / "disease_thresholds.json"
    cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
    state["thresholds"] = cfg.get("thresholds", {})
    state["tta"] = bool(cfg.get("use_tta", False))
    # warm-up so the first real request is not slow
    dummy = np.zeros((IMGSZ // 2, IMGSZ, 3), np.uint8)
    state["disease"].predict(dummy, imgsz=IMGSZ, device=DEVICE, verbose=False)
    yield
    state.clear()


app = FastAPI(title="DENTEX Assistant API", version="1.0", lifespan=lifespan,
              description=DISCLAIMER)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


def iou_xyxy(a, b) -> float:
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def assign_tooth(box, teeth):
    """FDI number of the tooth that best matches the finding box (or None)."""
    best, best_fdi = 0.05, None
    for fdi, tb in teeth:
        iw = max(0.0, min(box[2], tb[2]) - max(box[0], tb[0]))
        ih = max(0.0, min(box[3], tb[3]) - max(box[1], tb[1]))
        cover = iw * ih / max(1e-6, (box[2] - box[0]) * (box[3] - box[1]))  # share of finding inside tooth
        score = max(iou_xyxy(box, tb), cover * 0.5)
        if score > best:
            best, best_fdi = score, fdi
    return best_fdi


def merge_caries_findings(findings):
    """Merge overlapping Caries / Deep Caries boxes into one 'Caries' finding with a depth hint."""
    fam = sorted((f for f in findings if f["label"] in CARIES_FAMILY), key=lambda f: -f["confidence"])
    rest = [f for f in findings if f["label"] not in CARIES_FAMILY]
    kept = []
    for f in fam:
        if any(iou_xyxy(f["bbox_xyxy"], k["bbox_xyxy"]) > 0.5 for k in kept):
            continue
        kept.append(f)
    for k in kept:
        k["depth"] = "possibly deep" if k["label"] == "Deep Caries" else "standard"
        k["label"] = "Caries"
    return rest + kept


def decode_image(data: bytes):
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)   # BGR, what YOLO expects
    if img is None:
        raise HTTPException(400, "Could not decode the file as an image (use PNG or JPG).")
    return img


@app.get("/", include_in_schema=False)
def demo_page():
    return FileResponse(BASE / "demo.html")


@app.get("/health")
def health():
    return {"status": "ok", "disease_model": "disease" in state,
            "tooth_model": state.get("tooth") is not None,
            "thresholds": state.get("thresholds"), "use_tta": state.get("tta")}


@app.post("/analyze")
def analyze(
    file: UploadFile = File(..., description="Panoramic dental X-ray (PNG/JPG)"),
    sensitivity: float = Query(1.0, ge=0.5, le=2.0,
                               description="Higher = more findings (lower thresholds), lower = fewer, more confident findings"),
    group_caries: bool = Query(True, description="Show Caries / Deep Caries as one 'Caries' class with a depth hint"),
    include_tooth_numbers: bool = Query(True, description="Estimate the FDI tooth number of each finding"),
):
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, f"File too large (limit {MAX_BYTES // 1024 // 1024} MB).")
    img = decode_image(data)
    h, w = img.shape[:2]

    names = state["disease"].names
    thr = state["thresholds"]
    base_conf = max(0.01, min([thr.get(n, 0.25) for n in names.values()]) / 2.0)   # sensitivity can halve thresholds

    t0 = time.perf_counter()
    with lock:
        r = state["disease"].predict(img, imgsz=IMGSZ, conf=base_conf, iou=0.6, augment=state["tta"],
                                     device=DEVICE, verbose=False)[0]
        teeth = []
        if include_tooth_numbers and state["tooth"] is not None:
            rb = state["tooth"].predict(img, imgsz=IMGSZ, conf=0.25, iou=0.5, device=DEVICE, verbose=False)[0]
            tnames = state["tooth"].names
            teeth = [(int(tnames[int(c)]), xy.tolist()) for c, xy in
                     zip(rb.boxes.cls.cpu().numpy(), rb.boxes.xyxy.cpu().numpy())]
    ms = round((time.perf_counter() - t0) * 1000)

    findings = []
    for c, s, xy in zip(r.boxes.cls.cpu().numpy(), r.boxes.conf.cpu().numpy(), r.boxes.xyxy.cpu().numpy()):
        label = names[int(c)]
        limit = min(0.99, max(0.01, thr.get(label, 0.25) / sensitivity))
        if float(s) < limit:
            continue
        box = [round(float(v), 1) for v in xy]
        findings.append({"label": label, "confidence": round(float(s), 3), "depth": None,
                         "tooth_fdi": assign_tooth(box, teeth) if teeth else None, "bbox_xyxy": box})
    if group_caries:
        findings = merge_caries_findings(findings)
    findings.sort(key=lambda f: -f["confidence"])
    for i, f in enumerate(findings, 1):
        f["id"] = i

    return {"image": {"width": w, "height": h}, "findings": findings, "inference_ms": ms,
            "settings": {"sensitivity": sensitivity, "group_caries": group_caries},
            "tooth_numbers_are_estimates": True, "disclaimer": DISCLAIMER}