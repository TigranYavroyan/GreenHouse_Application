"""
Utilities for turning arbitrary JSON-like Python data (dicts/lists/scalars)
into simple, user-friendly table structures.

Designed to keep JSON handling generic and reusable, following SOLID and KISS:
- Single Responsibility: this module only knows how to extract and prettify data.
- Open/Closed: callers can extend behaviour by post-processing rows if needed.
- KISS: no heavy abstractions, just small pure functions.
"""

from typing import Any, List, Tuple


def prettify_key(key: str) -> str:
    """
    Convert a technical key name into a human-readable label.

    Examples:
        "soil_moisture" -> "Soil Moisture"
        "sensorValue"   -> "Sensor Value"
    """
    if not isinstance(key, str):
        return str(key)

    # Replace underscores with spaces
    key = key.replace("_", " ")

    # Split simple camelCase by inserting spaces before capitals
    pretty = ""
    prev_lower = False
    for ch in key:
        if ch.isupper() and prev_lower:
            pretty += " " + ch
        else:
            pretty += ch
        prev_lower = ch.islower()

    return pretty.strip().title()


def extract_payload(response: Any) -> Any:
    """
    Extract the most relevant payload part from a typical command response.

    Tries common keys like "result" or "data" first, then falls back to
    the whole response. This keeps callers free from repeating the same
    extraction logic.
    """
    if not isinstance(response, dict):
        return response

    # Ordered by typical importance
    for key in ("result", "data", "payload"):
        if key in response:
            return response.get(key)

    return response


def build_user_friendly_rows(
    payload: Any,
    summary_text: str = "",
) -> Tuple[List[str], List[List[str]]]:
    """
    Turn an arbitrary JSON-like payload into table (columns, rows) suitable
    for non-technical users.

    - Avoids technical paths like "data.temp" or nested JSON dumps.
    - Uses simple "Property | Value" or "Item" layouts.
    - If the payload is effectively identical to the already-visible
      summary_text, it returns a minimal informational row instead of
      repeating the same content again.
    """
    # Normalise summary text (e.g. strip "(Cached: Yes/No)")
    base_summary = summary_text.split("(Cached:")[0].strip() if summary_text else ""

    # Dict payload -> Property/Value table
    if isinstance(payload, dict):
        columns = ["Property", "Value"]
        rows: List[List[str]] = []

        # For keys that typically hold the actual JSON result (e.g. "data", "output"),
        # we want to expand their inner dict into separate rows so that users see:
        #   soilPH -> 6.56
        #   unit   -> pH
        # rather than a single "{'soilPH': 6.56, ...}" blob.
        EXPAND_KEYS = {"data", "output", "payload", "result"}
        expanded_signatures = set()

        def _looks_like_raw_blob(raw_value: Any) -> bool:
            """Detect values that represent full nested payload dumps."""
            if isinstance(raw_value, (dict, list)):
                return True
            if isinstance(raw_value, str):
                text = raw_value.strip()
                return (text.startswith("{") and text.endswith("}")) or (
                    text.startswith("[") and text.endswith("]")
                )
            return False

        for raw_key, value in payload.items():
            key_lower = str(raw_key).lower()

            # Hide redundant technical dump rows in details view.
            if key_lower == "output" and _looks_like_raw_blob(value):
                continue

            if isinstance(value, dict) and key_lower in EXPAND_KEYS:
                # Try to avoid duplicating identical dicts under different keys
                sig = None
                try:
                    sig = ("dict", tuple(sorted(value.items())))
                except TypeError:
                    # Non-hashable values inside dict; skip dedup optimisation
                    pass

                if sig is not None and sig in expanded_signatures:
                    # We've already expanded an identical payload (e.g. both
                    # "output" and "data" contain the same dict) – skip.
                    continue
                if sig is not None:
                    expanded_signatures.add(sig)

                for inner_key, inner_value in value.items():
                    label = prettify_key(inner_key)
                    value_str = str(inner_value)
                    rows.append([label, value_str])
            else:
                label = prettify_key(raw_key)
                value_str = str(value)
                rows.append([label, value_str])

        # If there is only one row and it matches the summary, avoid duplication
        if len(rows) == 1 and base_summary:
            if rows[0][1] == base_summary or rows[0][1] in base_summary:
                return ["Info", "Value"], [["Info", "No additional details beyond the main result."]]

        return columns, rows

    # List payload -> one item per row
    if isinstance(payload, list):
        # If the list is a list of scalars, keep it very simple
        if all(not isinstance(item, (dict, list)) for item in payload):
            columns = ["Item"]
            rows = [[str(item)] for item in payload]

            if len(rows) == 1 and base_summary:
                if rows[0][0] == base_summary or rows[0][0] in base_summary:
                    return ["Info"], [["No additional details beyond the main result."]]

            return columns, rows

        # If items are dicts/lists, fall back to a simple indexed list
        columns = ["Item #", "Value"]
        rows = []
        for idx, item in enumerate(payload, 1):
            rows.append([str(idx), str(item)])
        return columns, rows

    # Scalar payload
    value_str = str(payload)
    if base_summary and (value_str == base_summary or value_str in base_summary):
        return ["Info"], [["No additional details beyond the main result."]]

    return ["Result"], [[value_str]]

