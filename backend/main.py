import io
import os
import random

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel, Field
from supabase import create_client
import logging
from llm import ENABLED as LLM_ENABLED, MODEL as LLM_MODEL, finalize, generate



load_dotenv()

log = logging.getLogger("uvicorn.error")
# Service-role client: bypasses RLS. Every query below must therefore check ownership by hand.
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

VISION_URL = os.environ.get("VISION_URL", "mock")   # "mock" = fake results, no model needed
RAG_URL = os.environ.get("RAG_URL", "http://127.0.0.1:8001")
REVIEW_BELOW = 0.40  # findings under this confidence get flagged "needs human review" (my choice, tune it)

app = FastAPI(title="DentIA backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")],
    allow_methods=["*"],
    allow_headers=["*"],
)


def current_user(authorization: str | None = Header(default=None)):
    """Validates the Supabase access token sent by the browser and returns the user."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    try:
        user = sb.auth.get_user(authorization.removeprefix("Bearer ")).user
    except Exception:
        raise HTTPException(401, "Invalid token")
    if user is None:
        raise HTTPException(401, "Invalid token")
    return user


# ----------------------------------------------------------------------------------
# VISION
# Output format = the DENTEX service's own format:
#   bbox_xyxy = [x1, y1, x2, y2] in PIXELS of the original image
#   label = Caries | Impacted | Periapical Lesion | ..., depth, tooth_fdi (an ESTIMATE)
# ----------------------------------------------------------------------------------
def mock_vision(image_bytes: bytes, seed: str) -> dict:
    rng = random.Random(seed)  # same radiograph -> same fake result
    w, h = Image.open(io.BytesIO(image_bytes)).size
    findings = []
    for i in range(rng.randint(2, 4)):
        x1, y1 = rng.uniform(0.1, 0.7) * w, rng.uniform(0.3, 0.6) * h
        findings.append({
            "id": i + 1,
            "label": rng.choice(["Caries", "Impacted", "Periapical Lesion"]),
            "confidence": round(rng.uniform(0.3, 0.95), 3),
            "depth": None,
            "tooth_fdi": rng.choice([18, 26, 36, 46, 48]),
            "bbox_xyxy": [round(x1, 1), round(y1, 1),
                          round(x1 + rng.uniform(0.04, 0.08) * w, 1),
                          round(y1 + rng.uniform(0.08, 0.15) * h, 1)],
        })
    return {"image": {"width": w, "height": h}, "findings": findings}


def real_vision(image_bytes: bytes, filename: str) -> dict:
    try:
        r = httpx.post(
            f"{VISION_URL}/analyze",
            files={"file": (filename, image_bytes, "application/octet-stream")},
            params={"sensitivity": 1.0, "group_caries": True, "include_tooth_numbers": True},
            timeout=180,  # CPU inference can take several seconds
        )
    except httpx.HTTPError as e:
        raise RuntimeError(f"Vision service unreachable: {e}")
    if r.status_code != 200:
        raise RuntimeError(f"Vision service error {r.status_code}: {r.text[:200]}")
    return r.json()


def run_vision(image_bytes: bytes, filename: str, seed: str):
    if VISION_URL == "mock":
        raw = mock_vision(image_bytes, seed)
        info = {"vision": "mock", "mock": True}
    else:
        raw = real_vision(image_bytes, filename)
        info = {
            "vision": "dentex-yolo",
            "mock": False,
            "inference_ms": raw.get("inference_ms"),
            "settings": raw.get("settings"),
            "tooth_numbers_are_estimates": True,
            "disclaimer": raw.get("disclaimer"),
        }
    findings = raw["findings"]
    for f in findings:
        f["needs_review"] = f["confidence"] < REVIEW_BELOW
    return findings, info, raw["image"]


class AnalysisRequest(BaseModel):
    radiograph_id: str


@app.get("/health")
def health():
    return {"status": "ok", "vision": "mock" if VISION_URL == "mock" else VISION_URL}


@app.post("/analyses")
def create_analysis(body: AnalysisRequest, user=Depends(current_user)):
    # 1. The radiograph must belong to the caller
    rg = (sb.table("radiographs")
          .select("id, storage_path, kind")
          .eq("id", body.radiograph_id)
          .eq("doctor_id", user.id)
          .limit(1)
          .execute())
    if not rg.data:
        raise HTTPException(404, "Radiograph not found")
    radiograph = rg.data[0]

    # 2. Create the row as pending
    created = (sb.table("analyses")
               .insert({"doctor_id": user.id, "radiograph_id": radiograph["id"], "status": "pending"})
               .execute())
    analysis_id = created.data[0]["id"]

    # 3. Fetch the image, run the model, store the result
    try:
        image = sb.storage.from_("radiographs").download(radiograph["storage_path"])
        filename = radiograph["storage_path"].rsplit("/", 1)[-1]
        findings, model_info, dims = run_vision(image, filename, seed=radiograph["id"])

        # the real image size, needed later to draw the boxes
        sb.table("radiographs").update(
            {"width": dims["width"], "height": dims["height"]}
        ).eq("id", radiograph["id"]).execute()

        done = (sb.table("analyses")
                .update({"status": "completed", "findings": findings, "model_info": model_info})
                .eq("id", analysis_id)
                .execute())
        return done.data[0]
    except Exception as e:
        sb.table("analyses").update({"status": "failed", "error": str(e)[:500]}).eq("id", analysis_id).execute()
        raise HTTPException(502, "Analysis failed")


class AssistantRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    patient_id: str
    radiograph_id: str | None = None


@app.post("/assistant")
def ask_assistant(body: AssistantRequest, user=Depends(current_user)):
    # ownership checks (this client bypasses RLS)
    patient = (sb.table("patients").select("id")
               .eq("id", body.patient_id).eq("doctor_id", user.id).limit(1).execute())
    if not patient.data:
        raise HTTPException(404, "Patient not found")
    if body.radiograph_id:
        rg = (sb.table("radiographs").select("id")
              .eq("id", body.radiograph_id).eq("doctor_id", user.id)
              .eq("patient_id", body.patient_id).limit(1).execute())
        if not rg.data:
            raise HTTPException(404, "Radiograph not found")

    try:
        r = httpx.post(f"{RAG_URL}/search", json={"query": body.question, "top_k": 3}, timeout=30)
        r.raise_for_status()
        data = r.json()
    except httpx.HTTPError:
        raise HTTPException(502, "Literature search unavailable")

    retrieved = [
        {"n": i + 1, "title": x["title"], "authors": x["authors"], "journal": x["journal"],
         "year": x["year"], "doi": x["doi"], "url": x["url"], "passage": x["passage"]}
        for i, x in enumerate(data["results"])
    ]

    answer, citations, insufficient, model_used = "", [], False, None

    if not retrieved:
        insufficient = True
    elif LLM_ENABLED:
        try:
            out = generate(body.question, retrieved)
            if not out["sufficient"]:
                insufficient = True
            else:
                answer, order = finalize(out["answer"], len(retrieved))
                # keep only the sources the answer cites, renumbered to match the text
                citations = [{**retrieved[o - 1], "n": i} for i, o in enumerate(order, 1)]
                model_used = LLM_MODEL
        except Exception as e:
            log.warning("LLM step failed, falling back to raw passages: %s", e)
            answer, citations, insufficient = "", [], False

    if not insufficient and model_used is None:
        citations = retrieved  # fallback: raw passages, no generated text

    row = {
        "doctor_id": user.id,
        "patient_id": body.patient_id,
        "question": body.question.strip(),
        "answer": answer,
        "citations": citations,
        "insufficient_evidence": insufficient,
        "llm_model": model_used,
    }
    if body.radiograph_id:
        row["radiograph_id"] = body.radiograph_id
    try:
        saved = sb.table("assistant_queries").insert(row).execute()
    except Exception as e:
        raise HTTPException(500, f"Could not save the search: {e}")
    return saved.data[0]
    # ownership checks (this client bypasses RLS)
    patient = (sb.table("patients").select("id")
               .eq("id", body.patient_id).eq("doctor_id", user.id).limit(1).execute())
    if not patient.data:
        raise HTTPException(404, "Patient not found")
    if body.radiograph_id:
        rg = (sb.table("radiographs").select("id")
              .eq("id", body.radiograph_id).eq("doctor_id", user.id)
              .eq("patient_id", body.patient_id).limit(1).execute())
        if not rg.data:
            raise HTTPException(404, "Radiograph not found")

    try:
        r = httpx.post(f"{RAG_URL}/search", json={"query": body.question, "top_k": 3}, timeout=30)
        r.raise_for_status()
        data = r.json()
    except httpx.HTTPError:
        raise HTTPException(502, "Literature search unavailable")

    # Copy of each source at the time of the question (a saved report must never depend on the RAG index)
    citations = [
        {"n": i + 1, "title": x["title"], "authors": x["authors"], "journal": x["journal"],
         "year": x["year"], "doi": x["doi"], "url": x["url"], "passage": x["passage"]}
        for i, x in enumerate(data["results"])
    ]
    insufficient = data["insufficient_evidence"]
    # No LLM yet: the "answer" is just the retrieved passages, numbered. Nothing is generated.
    answer = "" if insufficient else "\n".join(f"[{c['n']}] {c['passage']}" for c in citations)

    row = {
        "doctor_id": user.id,
        "patient_id": body.patient_id,
        "question": body.question.strip(),
        "answer": answer,
        "citations": citations,
        "insufficient_evidence": insufficient,
    }
    if body.radiograph_id:
        row["radiograph_id"] = body.radiograph_id
    saved = sb.table("assistant_queries").insert(row).execute()
    return saved.data[0]