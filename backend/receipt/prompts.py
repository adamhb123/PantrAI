"""Prompts for receipt_llm.py

Ideas:
    1. Limit possible product names to items in OpenFood db
"""


# Final pass subprompts
_ROLE = """\
"You are a receipt parser. Extract the purchased items from this receipt image.\n\n"
"Respond ONLY with valid JSON matching this exact schema — no explanation, no markdown, no code fences:\n"""

_SCHEMA = """\
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

_RULES = """\
Rules:
- Include ONLY purchased products.
- Exclude everything else: totals, taxes, payment lines, store address, receipt metadata, bag fees, bottle deposits, and any discounts, coupons, savings, or loyalty rewards (even if they appear as line items with a negative or positive price).
- If a line has a multiplier like "2 @ 2.99", set quantity=2 and unit_price=2.99.
- The product price is almost always included horizontally to the item itself, either to the left or to the right.
- If the same product appears on multiple lines, merge them into a single item and sum the quantities.
- If a price cannot be determined, set it to null."""


PROMPT_FIRST_PASS = "This image contains a receipt. Describe what you see in this image in one sentence."
#PROMPT_SECOND_PASS = "This image contains a receipt. List every purchased food or beverage item you can read, one per line, with its price if visible. Ignore totals, taxes, coupons, discounts, and fees."
PROMPT_FINAL_PASS =  _ROLE + '\n' + _SCHEMA + "\n\n" + _RULES

