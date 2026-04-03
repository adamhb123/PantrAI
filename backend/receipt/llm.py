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

from datetime import datetime
from enum import Enum
import json
import numpy as np
import os
import re
import ollama
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
from dotenv import load_dotenv

# Local imports
from util import image_to_b64, load_images
from prompts import PROMPTS_ITEM, PROMPTS_RECEIPT 

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

def chat_with_vision_model(image: str | np.ndarray, model: str, prompts: List[str], final_prompt_temperature: float|None=0.0, forward_prompts=True) -> str | None:
    """
    Sends an image to a vision model via Ollama.

    Args:
        image_path: Path to the image file.

    Returns:
        The model's response as a string.
    """
    try:
        ollama.generate(model=VISION_MODEL, prompt='', keep_alive=0)
        _b64 = image_to_b64(image)
        # First pass
        print(f"[debug] image b64 length: {len(_b64)}")
        last_prompt = prompts[0]
        last_result = ollama.chat(model=model, messages=[{
            "role": "user",
            "content": last_prompt,
            "images": [_b64],
        }])
        for i,  prompt in enumerate(prompts):
            if i == 0:
                continue
            cur_prompt = prompt if not forward_prompts else _combine_outputs_and_prompt( # This may be useless
                [(last_prompt, str(last_result.message.content))],
                prompt
            ) 
            options = {"temperature": final_prompt_temperature} if i == len(prompts)-1 and \
                final_prompt_temperature is not None else {}
            last_result = ollama.chat(model=model, messages=[
            {
                "role": "user",
                "content": cur_prompt,
                "images": [_b64]
            },
            ], options=options)
            last_prompt = cur_prompt
        # Unload model
        ollama.generate(model=VISION_MODEL, prompt='', keep_alive=0)
        return last_result.message.content
    except FileNotFoundError:
        return "Error: Image file not found."
    except Exception as e:
        return f"An error occurred: {e}"

class ParseType(Enum):
    Receipt=0
    Item=1
    
@dataclass
class ParseItem:
    pass

@dataclass
class ParseResult:
    pass

@dataclass
class ItemItem(ParseItem):
    name: str
    generic_name: str
    quantity: int

@dataclass
class ItemResult(ParseResult):
    items: List[ItemItem]
    date: str

@dataclass
class ReceiptItem(ParseItem):
    name: str
    generic_name: str
    quantity: int
    unit_price: Optional[float]
    total_price: Optional[float]


@dataclass
class ReceiptResult(ParseResult):
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


def _parse_response(raw: str, parse_type: ParseType) -> ParseResult:
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    data = json.loads(raw)
    if parse_type == ParseType.Receipt:
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
        res = ReceiptResult(items=items, store=data.get("store"), date=data.get("date"))
    else: #elif parse_type == ParseType.Item:
        items = [
            ItemItem(
                name=item["name"],
                generic_name=item["generic_name"],
                quantity=item.get("quantity", 1),
            )
            for item in data.get("items", [])
        ]
        res = ItemResult(items=items, date=datetime.now().strftime("%Y-%m-%d"))
    return res

def extract_items_llm_only(image: str | np.ndarray,
                           model: str,
                           parse_type: ParseType) -> ParseResult | None:
    """Send the image directly to a vision LLM. No preprocessing."""
    prompts = PROMPTS_RECEIPT if parse_type==ParseType.Receipt else PROMPTS_ITEM
    response = chat_with_vision_model(image, model=model, prompts=prompts)
    if not response:
        return None
    return _parse_response(response, parse_type)

def extract_items_llm_only_multi(images: List[str] | List[np.ndarray],
                                 model,
                                 parse_type: ParseType) -> List[ReceiptResult | None]:
    responses = []
    for image in images:
        responses.append(extract_items_llm_only(image, model, parse_type))
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
    #images = load_images("./","jpg")
    #transformed = frames_transform(images, debug=True) this actually performs worse I think?
    #print(extract_items_llm_only_multi(images, model=VISION_MODEL, parse_type=ParseType.Receipt))
    images = ["banana.png"]
    print(extract_items_llm_only_multi(images, model=VISION_MODEL, parse_type=ParseType.Item))