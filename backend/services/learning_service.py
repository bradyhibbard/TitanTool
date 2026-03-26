"""
Learning service — manages the feedback loop that improves detection over time.

Phase 1 (MVP): Store accept/reject decisions + crops as labeled training data.
Phase 2:        Compute per-symbol score calibration from feedback statistics.
Phase 3:        Train a lightweight CNN on accumulated crops (planned).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..models_db import DetectionFeedback, SymbolResult

TRAINING_DATA_DIR = Path(__file__).resolve().parents[2] / "training_data"
TRAINING_DATA_DIR.mkdir(exist_ok=True)


# ────────────────────────────────────────────────────────────
# Record feedback
# ────────────────────────────────────────────────────────────

def record_feedback(
    db: Session,
    symbol_result_id: str,
    bbox: list[int],
    decision: str,
    scores: dict[str, float],
    search_region_path: str | None = None,
) -> DetectionFeedback:
    """
    Persist a single accept/reject decision and optionally crop + save the
    detected symbol image for future training.
    """
    sr: SymbolResult = db.get(SymbolResult, symbol_result_id)
    if sr is None:
        raise ValueError(f"SymbolResult {symbol_result_id!r} not found")

    crop_path = None
    if search_region_path:
        crop_path = _save_training_crop(
            search_region_path=Path(search_region_path),
            bbox=bbox,
            symbol_slug=sr.symbol_slug,
            decision=decision,
        )

    fb = DetectionFeedback(
        symbol_result_id=symbol_result_id,
        symbol_slug=sr.symbol_slug,
        bbox=bbox,
        combined_score=scores.get("combined_score", 0.0),
        binary_score=scores.get("binary_score", 0.0),
        edge_score=scores.get("edge_score", 0.0),
        iou_score=scores.get("iou_score", 0.0),
        decision=decision,
        crop_image_path=str(crop_path) if crop_path else None,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb


# ────────────────────────────────────────────────────────────
# Score calibration (Phase 2 — adaptive thresholds)
# ────────────────────────────────────────────────────────────

def compute_symbol_calibration(db: Session, symbol_slug: str) -> dict[str, Any]:
    """
    Compute simple stats from feedback for one symbol slug.
    Returns suggested threshold adjustments based on accepted/rejected scores.
    """
    rows = (
        db.query(DetectionFeedback)
        .filter(DetectionFeedback.symbol_slug == symbol_slug)
        .all()
    )

    if not rows:
        return {"symbol_slug": symbol_slug, "sample_count": 0, "suggestion": "no data yet"}

    accepted = [r for r in rows if r.decision == "accept"]
    rejected = [r for r in rows if r.decision == "reject"]

    def _avg(items, attr):
        vals = [getattr(i, attr) for i in items]
        return sum(vals) / len(vals) if vals else 0.0

    result: dict[str, Any] = {
        "symbol_slug": symbol_slug,
        "sample_count": len(rows),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "accepted_avg_combined": _avg(accepted, "combined_score"),
        "rejected_avg_combined": _avg(rejected, "combined_score"),
        "accepted_avg_binary": _avg(accepted, "binary_score"),
        "rejected_avg_binary": _avg(rejected, "binary_score"),
    }

    # Simple heuristic: suggest raising/lowering final_accept_score
    if len(accepted) >= 5 and len(rejected) >= 5:
        midpoint = (result["accepted_avg_combined"] + result["rejected_avg_combined"]) / 2
        result["suggested_accept_threshold"] = round(midpoint, 3)
        result["suggestion"] = "threshold recommendation available"
    else:
        result["suggestion"] = f"need more samples (have {len(rows)}, want ≥10 per class)"

    return result


def get_training_stats(db: Session) -> dict[str, Any]:
    """Return overall training data statistics."""
    total = db.query(DetectionFeedback).count()
    accepted = db.query(DetectionFeedback).filter(DetectionFeedback.decision == "accept").count()
    rejected = db.query(DetectionFeedback).filter(DetectionFeedback.decision == "reject").count()

    slugs = db.query(DetectionFeedback.symbol_slug).distinct().all()
    slug_counts = {}
    for (slug,) in slugs:
        count = db.query(DetectionFeedback).filter(DetectionFeedback.symbol_slug == slug).count()
        slug_counts[slug] = count

    return {
        "total_samples": total,
        "accepted": accepted,
        "rejected": rejected,
        "symbols": slug_counts,
        "training_data_dir": str(TRAINING_DATA_DIR),
    }


# ────────────────────────────────────────────────────────────
# Internal helpers
# ────────────────────────────────────────────────────────────

def _save_training_crop(
    search_region_path: Path,
    bbox: list[int],
    symbol_slug: str,
    decision: str,
) -> Path | None:
    try:
        from PIL import Image

        label_dir = TRAINING_DATA_DIR / symbol_slug / decision
        label_dir.mkdir(parents=True, exist_ok=True)

        existing = list(label_dir.glob("*.png"))
        idx = len(existing) + 1
        out_path = label_dir / f"{idx:05d}.png"

        with Image.open(search_region_path) as img:
            x1, y1, x2, y2 = bbox
            crop = img.crop((x1, y1, x2, y2))
            crop.save(out_path)

        return out_path
    except Exception as exc:  # noqa: BLE001
        print(f"[learning] Failed to save training crop: {exc}")
        return None
