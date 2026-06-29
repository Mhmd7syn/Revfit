# ST-GCN Exercise Classification — FastAPI Service

Wraps your existing inference pipeline (joint extraction → full-sequence
feature computation → post-hoc subsampling to `T_MAX=150` → ST-GCN model)
behind a `/predict` HTTP endpoint. The preprocessing logic is unchanged
from your script — only the structure changed, so it loads once and serves
many requests instead of running as a one-shot script.

## Files

- `model.py` — your joint extraction, feature extraction, ST-GCN model,
  and a new `STGCNPredictor` class that loads weights once and exposes
  `.predict(video_path)`.
- `main.py` — the FastAPI app. Loads the model at startup, exposes
  `POST /predict` and `GET /health`.
- `requirements.txt` — dependencies.
- `test_client.py` — a tiny example client.

## Setup

```bash
pip install -r requirements.txt
```

Set your model/encoder paths via environment variables (or just edit the
defaults at the top of `main.py`):

```bash
export MODEL_PATH=/kaggle/working/stgcn_output/best_stgcn_v2.pt
export ENCODER_PATH=/kaggle/working/stgcn_output/label_encoder.pkl
```

## Run

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

The model loads once at startup — check logs for `Model loaded and ready.`
Then visit `http://localhost:8000/docs` for interactive Swagger UI.

## Call it

```bash
curl -X POST "http://localhost:8000/predict?top_k=5" \
  -F "file=@/path/to/squat.mp4"
```

Or with the included client:

```bash
python test_client.py /path/to/squat.mp4
```

### Example response

```json
{
  "predicted_class": "squat",
  "confidence": 0.94,
  "top_k_classes": ["squat", "lunge", "deadlift", "burpee", "plank"],
  "top_k_probs": [0.94, 0.03, 0.01, 0.01, 0.01],
  "num_frames_used": 150,
  "num_frames_raw": 312,
  "inference_seconds": 1.42,
  "filename": "squat.mp4"
}
```

## Notes / design decisions

- **Model loads once at startup** (`@app.on_event("startup")`), not per
  request — this is the main perf win over running your script directly.
- **Preprocessing order is preserved exactly**: joints are extracted at
  native fps, features (pos/vel/acc/bone_ratio) are computed on the full
  sequence, and *then* subsampled to 150 frames — matching your training
  pipeline's `pad_collate`. Nothing was reordered.
- **Uploads are streamed to a temp file** (not loaded fully into memory)
  and cleaned up in a `finally` block even if inference fails.
- **`RuntimeError` from too few detected pose frames** is converted to a
  `422 Unprocessable Entity` instead of crashing the server.
- **CPU vs GPU**: `STGCNPredictor` auto-detects CUDA, same as your original
  script. If you're deploying on a GPU box, make sure `torch` is the CUDA
  build, not CPU-only.
- **Concurrency caveat**: MediaPipe's `Pose` instance is created fresh per
  call inside `video_to_joints`, so concurrent requests are safe in that
  regard. The model itself is used read-only (`eval()` + `no_grad()`), so
  concurrent requests sharing the single loaded `STGCNPredictor` are fine
  for inference. If you expect heavy concurrent load, consider running
  multiple uvicorn workers (`--workers N`) — each worker gets its own
  model copy in memory, so size accordingly.
- **Video formats**: I allowed `.mp4 .mov .avi .mkv .webm` by extension.
  Adjust `ALLOWED_EXTENSIONS` in `main.py` if you need more/fewer.
- **200MB upload cap** is just a safety default — change `MAX_UPLOAD_BYTES`
  if your videos are larger.
