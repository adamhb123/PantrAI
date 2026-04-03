"""Prompts for receipt_llm.py

Ideas:
    1. Limit possible product names to items in OpenFoodFacts db
"""

########## ---------- RECEIPTS ---------- ##########
# Final pass subprompts
_R_ROLE = """\
"You are a receipt parser. Extract the purchased items from this receipt image.\n\n"
"Respond ONLY with valid JSON matching this exact schema — no explanation, no markdown, no code fences:\n"""

_R_SCHEMA = """\
{
    "items": [
        {
            "name": "<clean product name>",
            "generic_name": "<generic, general product name>
            "quantity": <integer, default 1>,
            "unit_price": <float or null>,
            "total_price": <float or null>
        }
    ],
    "store": "<store name or null>",
    "date": "<YYYY-MM-DD or null>"
}"""

_R_RULES = """\
Rules:
- Include ONLY purchased products.
- Exclude everything else: totals, taxes, payment lines, store address, receipt metadata, bag fees, bottle deposits, and any discounts, coupons, savings, or loyalty rewards (even if they appear as line items with a negative or positive price).
- If a line has a multiplier like "2 @ 2.99", set quantity=2 and unit_price=2.99.
- The product price is almost always included horizontally to the item itself, either to the left or to the right.
- If the same product appears on multiple lines, merge them into a single item and sum the quantities.
- If a price cannot be determined, set it to null."""


_PR_FIRST_PASS = "This image contains a receipt. Describe what you see in this image in one sentence."
#PROMPT_SECOND_PASS = "This image contains a receipt. List every purchased food or beverage item you can read, one per line, with its price if visible. Ignore totals, taxes, coupons, discounts, and fees."
_PR_FINAL_PASS =  _R_ROLE + '\n' + _R_SCHEMA + "\n\n" + _R_RULES

PROMPTS_RECEIPT = [
    _PR_FIRST_PASS,
    _PR_FINAL_PASS
]

########## ---------- ITEMS ---------- ##########
_I_ROLE = """\
You are a grocery item identifier. You are given an image of one or more items purchased from a store — not a receipt, not a barcode scan, but the physical item itself.
Respond ONLY with valid JSON matching this exact schema — no explanation, no markdown, no code fences:\
"""

_I_SCHEMA = """\
{
    "items": [
        {
            "name": "<clean product name, e.g. 'Apple', 'Bread'>",
            "generic_name": "<generic category, e.g. 'Fruit', 'Grain'>",
            "quantity": <integer, default 1>
        }
    ]
}"""

_I_RULES = """\
Rules:
- Identify only physical grocery or store-purchased items visible in the image.
- Do NOT identify barcoded, packaged products by their barcode — focus on what the item actually is.
- If multiple distinct items are visible, list each separately.
- If the same item appears more than once, merge into one entry and set quantity accordingly.
- Use a clean, specific name (e.g. 'Red Bell Pepper', not just 'Pepper').
- The generic_name should be a short, broad category (e.g. 'Vegetable', 'Fruit', 'Bread').
- Set date to today's date in YYYY-MM-DD format."""

_PI_FIRST_PASS = "This image contains one or more items purchased from a store. Describe what you see in one sentence."
_PI_FINAL_PASS = _I_ROLE + '\n' + _I_SCHEMA + "\n\n" + _I_RULES

PROMPTS_ITEM = [
    _PI_FIRST_PASS,
    _PI_FINAL_PASS
]