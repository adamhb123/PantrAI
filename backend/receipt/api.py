"""
api.py

FastAPI server exposing receipt extraction endpoints.

Endpoints:
  GET  /health              - liveness check
  POST /extract             - extract items from one or more base64-encoded images
"""

import base64
import numpy as np
import cv2
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from llm import extract_items_llm_only_multi, VISION_MODEL

app = FastAPI(title="PantrAI Receipt API")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ExtractRequest(BaseModel):
    # Each entry is a base64-encoded image string
    images: List[str]
    model: Optional[str] = None


class ReceiptItemOut(BaseModel):
    name: str
    generic_name: str
    quantity: int
    unit_price: Optional[float]
    total_price: Optional[float]


class ReceiptResultOut(BaseModel):
    store: Optional[str]
    date: Optional[str]
    items: List[ReceiptItemOut]


class ExtractResponse(BaseModel):
    results: List[Optional[ReceiptResultOut]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _b64_to_ndarray(b64: str) -> np.ndarray:
    """Decode a base64 image string to an OpenCV ndarray."""
    try:
        # Strip data URL prefix if present (e.g. "data:image/jpeg;base64,...")
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        img_bytes = base64.b64decode(b64)
        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("cv2.imdecode returned None — not a valid image")
        return img
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image data: {e}")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/extract-receipt", response_model=ExtractResponse)
def extract(request: ExtractRequest):
    images = [_b64_to_ndarray(b64) for b64 in request.images]
    model = request.model or VISION_MODEL

    results = extract_items_llm_only_multi(images, model=model)

    out = []
    for r in results:
        if r is None:
            out.append(None)
        else:
            out.append(ReceiptResultOut(
                store=r.store,
                date=r.date,
                items=[
                    ReceiptItemOut(
                        name=item.name,
                        generic_name=item.generic_name,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                        total_price=item.total_price,
                    )
                    for item in r.items
                ],
            ))

    return ExtractResponse(results=out)
