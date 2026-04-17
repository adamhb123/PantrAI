# PantrAI - AI Pantry App
PantrAI is an AI pantry android app that automatically logs
inventory input and stores it in a local db. (see root of git repository for all relevant code).

## Architecture Overview
The app consists of a Flutter frontend and a Python FastAPI backend. The backend runs locally and exposes a REST API. All AI processing is done server-side using a locally-hosted vision LLM via Ollama (default model: `gemma3:12b`). The frontend communicates with the backend over HTTP.

## Screens
The app has two primary screens, each of which are accessible by pressing the relevant icons in the bottom app navigation bar.

### Home (Inventory) Screen
The Home screen shows the current state of the inventory. It lists each item (row) in the inventory db, with the item name, and an editable quantity column. The item name should take up the majority of the width. Swiping right on an item (or changing the quantity to zero) should bring up a Delete Item Entry? dialogue where the user confirms or denies the deletion. Both quantity changes and deletions should be propagated to the backend immediately.

### Scan Screen
The scan screen is where the user scans their items into the inventory. The top level has 3 buttons: Barcode, Item, Receipt, each of which open up their relevant subscreens when selected.

#### Barcode Subscreen
The barcode subscreen opens the camera. The camera display covers the screen, and on the display show a rectangular guide with only borders (transparent fill) with curved edges that indicate where the user should align the rectangular UPC barcode to get the scan. The scan occurs live and automatically, requiring no input from the viewer to trigger the scan (it should always be scanning while the camera is open). Only 1D barcode formats are scanned (EAN-13, EAN-8, UPC-A, UPC-E, Code128, Code39, Code93, ITF14, Codabar) — 2D formats like QR codes are explicitly disallowed. Once at least N=10 scans returned the exact same barcode, we can be confident that it is correct, and the user is shown another subscreen with the item fetched from the backend food database api (with a POST of the UPC barcode to `/get-barcode-item`). The expected response will be JSON, and will contain the field `item-name`. The user is shown the resolved item name and a quantity selector (default 1), then can confirm to add it to the inventory.

#### Item Subscreen
The item subscreen lets the user photograph a single grocery item to identify it via the vision LLM. When opened, the camera is shown full-screen. The user taps a capture button to take a photo. The captured image is base64-encoded and POSTed to `/extract-items` on the backend. While the request is in flight, a loading indicator is shown. On success, the response contains a list of identified items — each with a `name`, `generic_name`, and `quantity`. The user is shown a confirmation screen listing the identified items with editable quantities. Confirming adds all items to the local inventory db.

**Request (`POST /extract-items`):**
```json
{ "images": ["<base64-encoded-jpeg>"] }
```

**Response:**
```json
{
  "results": [
    {
      "date": "YYYY-MM-DD",
      "items": [
        { "name": "string", "generic_name": "string", "quantity": 1 }
      ]
    }
  ]
}
```

#### Receipt Subscreen
The receipt subscreen lets the user photograph a store receipt to bulk-add its items to the inventory. When opened, the camera is shown full-screen with a portrait-oriented overlay guide indicating where to align the receipt. The user taps a capture button to take a photo. The image is base64-encoded and POSTed to `/extract-receipts` on the backend. While the request is in flight, a loading indicator is shown with a note that receipt processing may take a moment.

On success, the response contains the store name (if detected), the purchase date, and a list of items — each with a `name`, `generic_name`, `quantity`, `unit_price`, and `total_price`. The user is shown a scrollable confirmation screen listing all extracted items with editable quantities and the option to deselect items they don't want to add. Confirming adds the selected items to the local inventory db.

**Request (`POST /extract-receipts`):**
```json
{ "images": ["<base64-encoded-jpeg>"] }
```

**Response:**
```json
{
  "results": [
    {
      "store": "string | null",
      "date": "YYYY-MM-DD | null",
      "items": [
        {
          "name": "string",
          "generic_name": "string",
          "quantity": 1,
          "unit_price": 0.00,
          "total_price": 0.00
        }
      ]
    }
  ]
}
```

---

## Local Database Schema
The app maintains a local SQLite database with a single `inventory` table:

| Column       | Type    | Notes                        |
|--------------|---------|------------------------------|
| `id`         | INTEGER | Primary key, auto-increment  |
| `name`       | TEXT    | Product name (from backend)  |
| `generic_name` | TEXT  | Generic category             |
| `quantity`   | INTEGER | Current stock count          |

When an item is added whose `name` already exists in the table, the `quantity` is incremented rather than creating a duplicate row.

---

## Backend API
The backend is a FastAPI server run with `uvicorn api:app --reload` from `backend/receipt/`. All image data is transmitted as base64-encoded JPEG strings.

| Endpoint             | Method | Description                                      |
|----------------------|--------|--------------------------------------------------|
| `/health`            | GET    | Liveness check — returns `{"status": "ok"}`      |
| `/extract-receipts`  | POST   | Extract items from a receipt photo via vision LLM |
| `/extract-items`     | POST   | Extract items from an item photo via vision LLM   |
| `/get-barcode-item`  | POST   | Resolve a UPC barcode to an item name (TODO)      |

### Vision LLM
All image-based extraction uses a locally-hosted Ollama model. The default and primary model is `gemma3:12b`. The backend uses a two-pass prompting strategy: a first pass generates a general description for context, and a second pass (temperature=0.0) extracts structured JSON. Model can be overridden per-request via the optional `model` field in the request body.

---

## Error Handling
- If the backend returns an error or is unreachable, the app shows a snackbar with a user-friendly message and does not modify the local db.
- If the LLM returns an empty or unparseable result, the user is shown an error screen with an option to retake the photo.
- Network timeout for all API requests: 30 seconds.
