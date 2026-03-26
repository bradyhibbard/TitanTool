"""
Detection service — bridges FastAPI / DB with the existing takeoff CV pipeline.
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI
from sqlalchemy.orm import Session

# Allow importing the sibling `takeoff` package
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from takeoff.config import AppConfig
from takeoff.models import SymbolTemplate
from takeoff.pipeline import prepare_page_shared_assets, run_symbol_detection_for_page
from takeoff.symbol_library_manager import load_symbol_library, save_symbol_library

from ..models_db import DetectionJob, LegendEntry, Project, SymbolResult
from ..services.legend_service import extract_legend_entries

UPLOADS_DIR = ROOT / "uploads"
OUTPUT_DIR = ROOT / "output"
UPLOADS_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


def _make_config(project: Project, page_index: int) -> AppConfig:
    return AppConfig(
        pdf_path=str(project.pdf_path),
        page_index=page_index,
        plan_name=project.id,
        output_root_dir=OUTPUT_DIR,
        enable_user_review=False,   # web review replaces OpenCV window
    )


def _openai_client() -> OpenAI:
    import os
    api_key = os.getenv("OPENAI_API_KEY", "")
    return OpenAI(api_key=api_key)


# ────────────────────────────────────────────────────────────
# Job runner  (called from background thread)
# ────────────────────────────────────────────────────────────

def run_detection_job(job_id: str, db: Session) -> None:
    """
    Full detection pipeline for one job.
    Runs synchronously — call from a BackgroundTask or worker thread.
    """
    job: DetectionJob = db.get(DetectionJob, job_id)
    if job is None:
        return

    project: Project = db.get(Project, job.project_id)
    if project is None:
        return

    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    db.commit()

    try:
        config = _make_config(project, job.page_index)
        client = _openai_client()

        # ── 1. Prepare shared page assets (render PDF, detect legend via OpenAI) ──
        shared = prepare_page_shared_assets(client, config)

        job.page_image_path = str(shared["page_image_path"])
        job.legend_crop_path = str(shared["legend_crop_path"])
        job.search_region_path = str(shared["search_region_path"])
        job.legend_bbox = list(shared["legend_bbox_px"])
        job.plan_bbox = list(shared["plan_bbox_px"])
        db.commit()

        # ── 2. Auto-extract legend entries (new AI-powered step) ──
        legend_entries_db = _ensure_legend_entries(db, job, project, config, shared, client)

        # ── 3. Run detection for each enabled symbol ──
        enabled = [e for e in legend_entries_db if e.enabled and e.template_path]

        for entry in enabled:
            symbol = SymbolTemplate(
                name=entry.symbol_name,
                slug=entry.symbol_slug,
                template_path=Path(entry.template_path),
                enabled=True,
                metadata={"detection_overrides": entry.detection_overrides},
            )

            result_data = run_symbol_detection_for_page(
                client=client,
                config=config,
                symbol=symbol,
                shared_page_assets=shared,
            )

            # Persist result
            sr = SymbolResult(
                job_id=job.id,
                project_id=project.id,
                symbol_name=entry.symbol_name,
                symbol_slug=entry.symbol_slug,
                template_path=entry.template_path,
                matches=result_data.get("matches", []),
                match_count=result_data.get("match_count_inside_plan_outside_legend", 0),
                debug_matches_image_path=result_data.get("files", {}).get("debug_matches"),
            )
            db.add(sr)
            db.commit()

        job.status = "done"
        job.finished_at = datetime.now(timezone.utc)
        project.status = "done"
        db.commit()

    except Exception as exc:  # noqa: BLE001
        job.status = "error"
        job.error_message = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        project.status = "error"
        db.commit()
        raise


# ────────────────────────────────────────────────────────────
# Legend entry management
# ────────────────────────────────────────────────────────────

def _ensure_legend_entries(
    db: Session,
    job: DetectionJob,
    project: Project,
    config: AppConfig,
    shared: dict,
    client,
) -> list[LegendEntry]:
    """
    Check if legend entries already exist for this job; if not, auto-extract them.
    """
    existing = db.query(LegendEntry).filter(LegendEntry.job_id == job.id).all()
    if existing:
        return existing

    # Auto-extract symbols from the legend image
    raw_entries = extract_legend_entries(client, shared["legend_crop_path"], config.model_name)

    entries = []
    for entry_data in raw_entries:
        name = entry_data.get("name", "Unknown")
        slug = SymbolTemplate.make_slug(name)
        icon_bbox = entry_data.get("icon_bbox")  # [x1, y1, x2, y2] within legend crop

        # Crop the template image from the legend
        template_path = None
        if icon_bbox:
            template_path = _crop_legend_template(
                legend_crop_path=shared["legend_crop_path"],
                icon_bbox=icon_bbox,
                output_dir=config.symbol_library_dir / slug,
            )

        le = LegendEntry(
            project_id=project.id,
            job_id=job.id,
            symbol_name=name,
            symbol_slug=slug,
            icon_bbox_in_legend=icon_bbox,
            template_path=str(template_path) if template_path else None,
            enabled=True,
            detection_overrides={},
        )
        db.add(le)
        entries.append(le)

    db.commit()
    return entries


def _crop_legend_template(legend_crop_path: Path, icon_bbox: list, output_dir: Path) -> Path | None:
    """Crop a symbol icon from the legend image and save as template.png."""
    try:
        from PIL import Image
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "template.png"

        with Image.open(legend_crop_path) as img:
            x1, y1, x2, y2 = icon_bbox
            # Add a small border for better matching
            pad = 4
            w, h = img.size
            x1 = max(0, x1 - pad)
            y1 = max(0, y1 - pad)
            x2 = min(w, x2 + pad)
            y2 = min(h, y2 + pad)
            cropped = img.crop((x1, y1, x2, y2))
            cropped.save(out_path)

        return out_path
    except Exception:  # noqa: BLE001
        return None


# ────────────────────────────────────────────────────────────
# Manual template upload (user draws bbox in browser)
# ────────────────────────────────────────────────────────────

def save_manual_template(
    legend_crop_path: str,
    icon_bbox: list[int],
    output_dir: Path,
) -> Path:
    return _crop_legend_template(Path(legend_crop_path), icon_bbox, output_dir)
