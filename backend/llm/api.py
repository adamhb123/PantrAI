"""
api.py

FastAPI server exposing receipt extraction endpoints.

Endpoints:
  GET  /health                  - liveness check
  POST /extract-receipts        - extract items from one or more base64-encoded receipt images
  POST /extract-items           - extract items from one or more base64-encoded item images
  POST /get-barcode-items       - get items in openfoodfacts db from barcode strings
  """

import base64
import json as json_lib
import urllib.request
import numpy as np
import cv2
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from llm import ParseType, extract_items_llm_only_multi, VISION_MODEL
from prompts import PROMPTS_RECEIPT

app = FastAPI(title="PantrAI Receipt API")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ExtractRequest(BaseModel):
    # Each entry is a base64-encoded image string
    images: List[str]
    model: Optional[str] = None


class ItemItemOut(BaseModel):
    name: str
    generic_name: str
    quantity: int

class ItemResultOut(BaseModel):
    date: Optional[str]
    items: List[ItemItemOut]

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
    results: List[Optional[ReceiptResultOut | ItemResultOut]]


class BarcodeRequest(BaseModel):
    barcodes: List[str]


class BarcodeItemOut(BaseModel):
    barcode: str
    item_name: Optional[str]


class BarcodeResponse(BaseModel):
    results: List[BarcodeItemOut]


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


def _lookup_barcode(barcode: str) -> Optional[str]:
    """Return a product name for a barcode via Open Food Facts, or None."""
    url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PantrAI/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json_lib.loads(resp.read().decode())
        if data.get("status") == 1:
            product = data["product"]
            return (
                product.get("product_name")
                or product.get("product_name_en")
                or None
            )
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/extract-receipts", response_model=ExtractResponse)
def extract_receipts(request: ExtractRequest) -> ExtractResponse:
    images = [_b64_to_ndarray(b64) for b64 in request.images]
    model = request.model or VISION_MODEL

    results = extract_items_llm_only_multi(images, model, ParseType.Receipt)

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

@app.post("/extract-items", response_model=ExtractResponse)
def extract_items(request: ExtractRequest):
    images = [_b64_to_ndarray(b64) for b64 in request.images]
    model = request.model or VISION_MODEL

    results = extract_items_llm_only_multi(images, model, ParseType.Item)

    out = []
    for r in results:
        if r is None:
            out.append(None)
        else:
            out.append(ItemResultOut(
                date=r.date,
                items=[
                    ItemItemOut(
                        name=item.name,
                        generic_name=item.generic_name,
                        quantity=item.quantity,
                    )
                    for item in r.items
                ],
            ))

    return ExtractResponse(results=out)


@app.post("/get-barcode-items", response_model=BarcodeResponse)
def get_barcode_items(request: BarcodeRequest) -> BarcodeResponse:
    results = [
        BarcodeItemOut(barcode=bc, item_name=_lookup_barcode(bc))
        for bc in request.barcodes
    ]
    return BarcodeResponse(results=results)