"""
AI-powered legend entry extraction.

Uses a vision model to identify each symbol entry in the electrical legend,
returning the symbol name and the bounding box of its icon.
This replaces the manual OpenCV crop step with an automatic approach.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from takeoff.openai_utils import ask_model_for_json

LEGEND_SYMBOLS_PROMPT = """
You are analyzing an electrical legend from a residential floor plan.

Your job is to identify every distinct symbol entry in this legend image.
For each entry, return:
  - "name": the text label for this symbol (e.g. "Bath Fan", "Recessed Light", "Switch")
  - "icon_bbox": the bounding box of the SYMBOL ICON only (not the label text),
    as [x1, y1, x2, y2] in pixel coordinates within this image.
    Be precise — the icon is the small graphical symbol, not the text next to it.

Return a JSON object in this exact format:
{
  "entries": [
    {"name": "Bath Fan",        "icon_bbox": [10, 5, 40, 35]},
    {"name": "Recessed Light",  "icon_bbox": [10, 45, 40, 75]},
    ...
  ]
}

Rules:
- Include ALL symbol entries you can see.
- If you cannot determine a name, use a descriptive name like "Unknown Symbol 1".
- icon_bbox must be [left, top, right, bottom] pixel coords within this legend image.
- Do NOT include entries that are just header text (like "ELECTRICAL LEGEND").
- Return ONLY valid JSON with the "entries" key.
"""


def extract_legend_entries(client, legend_crop_path: Path, model_name: str) -> list[dict]:
    """
    Call vision model on the legend crop and return a list of:
      {"name": str, "icon_bbox": [x1, y1, x2, y2]}
    """
    try:
        result = ask_model_for_json(client, legend_crop_path, LEGEND_SYMBOLS_PROMPT, model=model_name)
        entries = result.get("entries", [])
        # Validate each entry has the expected fields
        valid = []
        for e in entries:
            if "name" in e and "icon_bbox" in e:
                bbox = e["icon_bbox"]
                if isinstance(bbox, list) and len(bbox) == 4:
                    valid.append({"name": e["name"], "icon_bbox": [int(v) for v in bbox]})
        return valid
    except Exception as exc:  # noqa: BLE001
        print(f"[legend_service] Failed to extract legend entries: {exc}")
        return []
