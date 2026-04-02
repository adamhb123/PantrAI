"""
receipt_llm.py

Two extraction methods:
  - extract_items_llm_only: sends the raw image directly to a local vision LLM (Ollama).
  - extract_items_ocr: runs OCR first (receipt_ocr.py), then sends the text to the LLM.

Expected JSON response schema:
{
    "items": [
        {
            "name": str,         # Clean product name, e.g. "Baba Ghanouj", "Brawny Paper Towels"
            "generic_name": str  # Generic type for product e.g. "Dip"
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
import cv2
import functools
import json
import numpy as np
import os
from pprint import pprint
import re
import ollama
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
from dotenv import load_dotenv

# Local imports
from ocr import load_images, frames_transform
from prompts import PROMPT_FIRST_PASS, PROMPT_FINAL_PASS#, PROMPT_SECOND_PASS

load_dotenv(Path(__file__).parent / "llm.env")

# Environment variables
VISION_MODEL      = os.environ.get("OLLAMA_VISION_MODEL", "gemma3:12b")
TEXT_MODEL        = os.environ.get("OLLAMA_TEXT_MODEL", "qwen2.5:7b")

def _combine_outputs_and_prompt(prompt_output_tup: List[Tuple[str, str]],
                                new_prompt: str):
    str_build = ""
    for output_prompt, output in prompt_output_tup:
        str_build += (f"Based on the following prompt: {output_prompt}\n" + \
                      f" we know that: {output}\n" + \
                        f"Use this information to do the following: {new_prompt}")
        
    return str_build

def chat_with_vision_model(image: str | np.ndarray, model) -> str | None:
    """
    Sends an image to a vision model via Ollama.

    Args:
        image_path: Path to the image file.

    Returns:
        The model's response as a string.
    """
    try:
        ollama.generate(model=VISION_MODEL, prompt='', keep_alive=0)
        if type(image) == str:
            with open(image, "rb") as f:
                _b64 = base64.b64encode(f.read()).decode("utf-8")
        elif type(image) == np.ndarray:
            _, buffer = cv2.imencode('.jpg', image)
            _b64 = base64.b64encode(buffer).decode('utf-8')
        else:
            raise TypeError("Invalid type for argument : 'image'")
       
        # First pass
        print(f"[debug] image b64 length: {len(_b64)}")
        _first_pass = ollama.chat(model=VISION_MODEL, messages=[{
            "role": "user",
            "content": PROMPT_FIRST_PASS,
            "images": [_b64],
        }])
        print(f"[debug] first pass response: {_first_pass.message.content}\n")
        
        # Second pass (excluding for now)
        """_second_pass = ollama.chat(model=VISION_MODEL, messages=[{
            "role": "user",
            "content": PROMPT_SECOND_PASS,
            "images": [_b64],
        }])
        print(f"[debug] second pass response: {_second_pass.message.content}\n")
        """
        # Final pass
        final_prompt = _combine_outputs_and_prompt( # This may be useless
            [(PROMPT_FIRST_PASS, str(_first_pass.message.content))],
            PROMPT_FINAL_PASS
        )
        response = ollama.chat(model=model, messages=[
          {
            "role": "user",
            "content": final_prompt,
            "images": [_b64]
          },
        ], options={"temperature": 0})
        pprint(response.message)
        ollama.generate(model=VISION_MODEL, prompt='', keep_alive=0)
        return response.message.content
    except FileNotFoundError:
        return "Error: Image file not found."
    except Exception as e:
        return f"An error occurred: {e}"

@dataclass
class ReceiptItem:
    name: str
    generic_name: str
    quantity: int
    unit_price: Optional[float]
    total_price: Optional[float]


@dataclass
class ReceiptResult:
    items: List[ReceiptItem]
    store: Optional[str]
    date: Optional[str]

    def to_json(self):
        return json.dumps({
            "store": self.store,
            "date": self.date,
            "items": [
                {
                    "name": item.name,
                    "generic_name": item.generic_name,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "total_price": item.total_price,
                }
                for item in self.items
            ]
        }, indent=4)


    def __repr__(self):
        lines = [f"Store: {self.store}  Date: {self.date}", "Items:"]
        for item in self.items:
            price_str = f"${item.total_price:.2f}" if item.total_price is not None else "?"
            lines.append(f"  x{item.quantity}  {item.name} ({item.generic_name})  {price_str}")
        return "\n".join(lines)


def _parse_response(raw: str) -> ReceiptResult:
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    data = json.loads(raw)
    items = [
        ReceiptItem(
            name=item["name"],
            generic_name=item["generic_name"],
            quantity=item.get("quantity", 1),
            unit_price=item.get("unit_price"),
            total_price=item.get("total_price"),
        )
        for item in data.get("items", [])
    ]
    return ReceiptResult(items=items, store=data.get("store"), date=data.get("date"))

def extract_items_llm_only(image: str | np.ndarray,
                           model: str) -> ReceiptResult | None:
    """Send the image directly to a vision LLM. No preprocessing."""
    response = chat_with_vision_model(image, model=model)
    if not response:
        return None
    return _parse_response(response)

def extract_items_llm_only_multi(images: List[str] | List[np.ndarray], model) -> List[ReceiptResult | None]:
    responses = []
    for image in images:
        responses.append(extract_items_llm_only(image, model))
    return responses




'''def extract_items_ocr(image_path: str,
                      model: str = TEXT_MODEL,
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

    response = client.chat.completions.create(
        model=model,
        temperature=0.0,
        messages=[{
            "role": "user",
            "content": _OCR_PROMPT.format(ocr_text=ocr_text),
        }],
    )
    return _parse_response(response.choices[0].message.content)
'''

if __name__=="__main__":
    images = load_images("./","jpg")
    images.reverse()
    #transformed = frames_transform(images, debug=True) this actually performs worse I think?
    print(extract_items_llm_only_multi(images, model=VISION_MODEL))