# DENTEX Assistant API

FastAPI service around your two trained models. **Decision-support only – the dentist always has the final say.**

```
dentex-api/
├── app.py
├── demo.html              # standalone demo UI, served at http://localhost:8000/
├── requirements.txt
└── models/
    ├── disease_best.pt
    ├── tooth_best.pt              (optional – without it, tooth numbers are simply omitted)
    └── disease_thresholds.json
```

## 1. Run it

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

- Demo UI: <http://localhost:8000/>
- Interactive API docs (Swagger): <http://localhost:8000/docs>
- Works on CPU (about 2–6 s per X-ray, depending on your laptop). With an NVIDIA GPU: `DEVICE=0 uvicorn app:app ...`

Settings (environment variables): `MODEL_DIR`, `IMGSZ` (keep 1280, the size you trained at), `DEVICE`, `MAX_UPLOAD_MB`, `CORS_ORIGINS` (default `*`, restrict it once you deploy).

## 2. Showing it to your classmates (≈5-minute demo)

1. **Start the server before the session** and open `http://localhost:8000/`. Have 3–4 X-rays ready, ideally some of your *validation* images (never ones used for training).
2. **Show the flow:** drop an X-ray → boxes appear with confidence and an *estimated* tooth number → click a finding in the side panel to highlight it → **Accept / Reject** each one. This is the "dentist has the final say" part.
3. **Show the sensitivity slider.** Lower = fewer, more confident findings. Higher = catches more, with more false alarms. Explain that the defaults were tuned per class on validation data and favour recall.
4. **Toggle "Group Caries / Deep Caries".** Explain that the model confuses these two (about a third of true caries were matched as deep caries in the confusion matrix), so the UI merges them into one "Caries" finding with a "possibly deep" hint.
5. **Be upfront about limits** (a good demo is an honest one): mAP50 ≈ 0.66 on a 101-image validation split, Impacted ≈ 0.95 AP50, caries and deep caries are the weak spots, tooth numbers are estimates.
6. **Show `/docs`** so the React/backend people see the API contract and can try it from the browser.

**Letting others try it from their own devices:** run a free tunnel next to the server, e.g. `cloudflared tunnel --url http://localhost:8000` (or `ngrok http 8000`) and share the URL it prints. Anyone with the link can use it while it runs – only use public/demo X-rays, never real patient data.

## 3. API

`POST /analyze` (multipart form, field `file`) – query parameters:

| param | default | meaning |
|---|---|---|
| `sensitivity` | 1.0 (0.5–2.0) | Divides the tuned thresholds. >1 = more findings |
| `group_caries` | true | Merge overlapping Caries/Deep Caries into one "Caries" with `depth` |
| `include_tooth_numbers` | true | Estimate the FDI tooth number per finding |

```bash
curl -F "file=@xray.png" "http://localhost:8000/analyze?sensitivity=1.2"
```

```json
{
  "image": {"width": 2943, "height": 1435},
  "findings": [
    {"id": 1, "label": "Caries", "confidence": 0.62, "depth": "possibly deep",
     "tooth_fdi": 36, "bbox_xyxy": [1210.4, 880.0, 1302.9, 975.5]}
  ],
  "inference_ms": 2840,
  "tooth_numbers_are_estimates": true,
  "disclaimer": "..."
}
```

`bbox_xyxy` is in pixels of the **original** uploaded image. `GET /health` reports which models loaded.

## 4. Using it from React later

```jsx
async function analyze(file, sensitivity = 1.0) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`http://localhost:8000/analyze?sensitivity=${sensitivity}`, { method: "POST", body: fd });
  if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText);
  return res.json();
}

// Overlay: render the X-ray <img> with position:relative, then absolutely position boxes
// using percentages so they scale with the image.
function Overlay({ result }) {
  const { width, height } = result.image;
  return result.findings.map(f => {
    const [x1, y1, x2, y2] = f.bbox_xyxy;
    return (
      <div key={f.id} title={`${f.label} ${Math.round(f.confidence * 100)}%`}
           style={{ position: "absolute", border: "2px solid orange",
                    left: `${(x1 / width) * 100}%`, top: `${(y1 / height) * 100}%`,
                    width: `${((x2 - x1) / width) * 100}%`, height: `${((y2 - y1) / height) * 100}%` }} />
    );
  });
}
```

Open `demo.html` as a reference for the whole interaction (accept/reject, sensitivity, selection) – it is plain JS, easy to port.
Tips for the React app: debounce the sensitivity slider (the demo uses 350 ms), keep Accept/Reject state in the frontend, and store the dentist's decisions – they are valuable feedback data for improving the model.

## 5. Deploying later

- It is a normal Python web service: a Dockerfile (`python:3.11-slim`, `pip install -r requirements.txt`, `CMD uvicorn app:app --host 0.0.0.0 --port 8000`) works on Render, Railway, Fly.io, or a Hugging Face Space. CPU is fine for a class project (the container needs ~2 GB RAM).
- Set `CORS_ORIGINS` to your frontend's URL, and never expose real patient data on a public demo.
- For a real product you would additionally need authentication, audit logging, data protection/consent and clinical validation – mention this in your report as future work.
