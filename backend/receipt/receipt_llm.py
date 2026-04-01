"""
receipt_llm.py

Two extraction methods:
  - extract_items_llm_only: sends the raw image directly to a local vision LLM (Ollama).
  - extract_items_ocr: runs OCR first (receipt_ocr.py), then sends the text to the LLM.

Expected JSON response schema:
{
    "items": [
        {
            "name": str,         # Clean product name, e.g. "Baba Ghanouj"
            "quantity": int,     # Number of units (default 1)
            "unit_price": float | null,  # Price per unit if detectable
            "total_price": float | null  # Line total if detectable
        },
        ...
    ],
    "store": str | null,         # Store name if detected
    "date": str | null           # Date in YYYY-MM-DD format if detected
}
"""

import base64
import json
import re
from dataclasses import dataclass
from typing import List, Optional

from openai import OpenAI

MODEL = "gemma3:12b"
OLLAMA_BASE_URL = "http://localhost:11434/v1"

_SCHEMA = """\
{
    "items": [
        {
            "name": "<clean product name>",
            "quantity": <integer, default 1>,
            "unit_price": <float or null>,
            "total_price": <float or null>
        }
    ],
    "store": "<store name or null>",
    "date": "<YYYY-MM-DD or null>"
}"""

_RULES = """\
Rules:
- Include only purchased items. Exclude totals, taxes, payment lines, store address, and receipt metadata.
- If a line has a multiplier like "2 @ 2.99", set quantity=2 and unit_price=2.99.
- If a price cannot be determined, set it to null."""

_IMAGE_PROMPT = (
    "You are a grocery receipt parser. Extract the purchased items from this receipt image.\n\n"
    "Respond ONLY with valid JSON matching this exact schema — no explanation, no markdown, no code fences:\n"
    + _SCHEMA + "\n\n" + _RULES
)

_OCR_PROMPT = (
    "You are a grocery receipt parser. The following is raw OCR text extracted from a receipt.\n"
    "The OCR may be imperfect: characters may be garbled and tokens may be split across lines.\n\n"
    "Respond ONLY with valid JSON matching this exact schema — no explanation, no markdown, no code fences:\n"
    + _SCHEMA + "\n\n" + _RULES + "\n\nRaw OCR text:\n\n{ocr_text}"
)


@dataclass
class ReceiptItem:
    name: str
    quantity: int
    unit_price: Optional[float]
    total_price: Optional[float]


@dataclass
class ReceiptResult:
    items: List[ReceiptItem]
    store: Optional[str]
    date: Optional[str]

    def __repr__(self):
        lines = [f"Store: {self.store}  Date: {self.date}", "Items:"]
        for item in self.items:
            price_str = f"${item.total_price:.2f}" if item.total_price is not None else "?"
            lines.append(f"  x{item.quantity}  {item.name}  {price_str}")
        return "\n".join(lines)


def _parse_response(raw: str) -> ReceiptResult:
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    data = json.loads(raw)
    items = [
        ReceiptItem(
            name=item["name"],
            quantity=item.get("quantity", 1),
            unit_price=item.get("unit_price"),
            total_price=item.get("total_price"),
        )
        for item in data.get("items", [])
    ]
    return ReceiptResult(items=items, store=data.get("store"), date=data.get("date"))


def extract_items_llm_only(image_path: str,
                           model: str = MODEL,
                           base_url: str = OLLAMA_BASE_URL) -> ReceiptResult:
    """Send the image directly to a vision LLM. No preprocessing."""
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    client = OpenAI(base_url=base_url, api_key="ollama")
    response = client.chat.completions.create(
        model=model,
        temperature=0.0,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": _IMAGE_PROMPT},
            ]
        }],
    )
    return _parse_response(response.choices[0].message.content)


def extract_items_ocr(image_path: str,
                      model: str = MODEL,
                      base_url: str = OLLAMA_BASE_URL) -> ReceiptResult:
    """Run OCR pipeline first (deskew + perspective correct), then send text to LLM."""
    from receipt_ocr import _load_images, _frames_select, _frames_transform, _easyocr

    frames = _load_images(image_path, "jpg")
    selected = _frames_select(frames)
    transformed = _frames_transform(selected)
    _, frame_results = _easyocr(transformed)

    ocr_text = "\n".join(
        r.text
        for fr in frame_results
        for r in fr.ocr_results
    )

    client = OpenAI(base_url=base_url, api_key="ollama")
    response = client.chat.completions.create(
        model=model,
        temperature=0.0,
        messages=[{
            "role": "user",
            "content": _OCR_PROMPT.format(ocr_text=ocr_text),
        }],
    )
    return _parse_response(response.choices[0].message.content)
