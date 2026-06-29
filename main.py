"""
FastAPI service — ST-GCN exercise classification from video
=============================================================
POST /predict  with a multipart video file  ->  JSON classification result

Run:
    uvicorn main:app --host 0.0.0.0 --port 8000

Env vars (override the defaults below if your paths differ):
    MODEL_PATH    - path to best_stgcn_v2.pt
    ENCODER_PATH  - path to label_encoder.pkl
"""

import os
import shutil
import tempfile
import time
import logging

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse

from model import STGCNPredictor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stgcn_api")

# ── Config ────────────────────────────────────────────────────────────────────
MODEL_PATH   = os.environ.get("MODEL_PATH", "/kaggle/working/stgcn_output/best_stgcn_v2.pt")
ENCODER_PATH = os.environ.get("ENCODER_PATH", "/kaggle/working/stgcn_output/label_encoder.pkl")

# Allowed upload extensions/content-types — extend as needed
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
MAX_UPLOAD_BYTES   = 200 * 1024 * 1024  # 200 MB safety cap

app = FastAPI(title="ST-GCN Exercise Classification API", version="1.0.0")

predictor = None  # populated at startup


@app.on_event("startup")
def load_model():
    """Load model + label encoder ONCE when the server starts, not per-request."""
    global predictor
    logger.info("Loading STGCN model and label encoder...")
    predictor = STGCNPredictor(model_path=MODEL_PATH, encoder_path=ENCODER_PATH)
    logger.info("Model loaded and ready.")


@app.get("/health")
def health():
    return {
        "status": "ok" if predictor is not None else "loading",
        "device": str(predictor.device) if predictor else None,
        "num_classes": predictor.num_classes if predictor else None,
    }


@app.post("/predict")
async def predict(file: UploadFile = File(...), top_k: int = 5):
    """
    Upload a video file and get back the predicted exercise class.

    Form-data field: `file` (the video)
    Optional query param: `top_k` (default 5)
    """
    if predictor is None:
        raise HTTPException(status_code=503, detail="Model is still loading, try again shortly.")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    # Stream upload to a temp file (avoids holding the whole video in memory)
    tmp_dir = tempfile.mkdtemp(prefix="stgcn_upload_")
    tmp_path = os.path.join(tmp_dir, f"input{ext}")

    try:
        size = 0
        with open(tmp_path, "wb") as out_f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="File too large.")
                out_f.write(chunk)

        logger.info(f"Saved upload '{file.filename}' ({size} bytes) -> {tmp_path}")

        t0 = time.time()
        try:
            result = predictor.predict(tmp_path, top_k=top_k)
        except RuntimeError as e:
            # e.g. "Too few frames with detected pose"
            raise HTTPException(status_code=422, detail=str(e))
        elapsed = time.time() - t0

        result["inference_seconds"] = round(elapsed, 3)
        result["filename"] = file.filename

        logger.info(
            f"Predicted '{result['predicted_class']}' "
            f"(conf={result['confidence']:.2%}) in {elapsed:.2f}s"
        )
        return JSONResponse(content=result)

    finally:
        # Always clean up the temp file/dir, even on error
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
