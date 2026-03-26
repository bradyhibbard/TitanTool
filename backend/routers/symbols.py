"""
/api/symbols  — Symbol results, legend entries, feedback, and takeoff summary
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models_db import DetectionJob, LegendEntry, Project, SymbolPreset, SymbolResult
from ..schemas import (
    FeedbackOut,
    FeedbackSubmit,
    LegendEntryOut,
    LegendEntryUpdate,
    MessageOut,
    SymbolResultOut,
    TakeoffSummary,
    TakeoffSummaryItem,
)
from ..services.learning_service import get_training_stats, record_feedback

router = APIRouter(prefix="/api", tags=["symbols"])


# ────────────────────────────────────────────────────────────
# Symbol results
# ────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/results", response_model=list[SymbolResultOut])
def get_results(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return (
        db.query(SymbolResult)
        .filter(SymbolResult.project_id == project_id)
        .order_by(SymbolResult.created_at.desc())
        .all()
    )


@router.get("/results/{result_id}", response_model=SymbolResultOut)
def get_result(result_id: str, db: Session = Depends(get_db)):
    sr = db.get(SymbolResult, result_id)
    if not sr:
        raise HTTPException(status_code=404, detail="Result not found")
    return sr


# ────────────────────────────────────────────────────────────
# Serve detection images
# ────────────────────────────────────────────────────────────

@router.get("/images/page/{project_id}/{job_id}")
def serve_page_image(project_id: str, job_id: str, db: Session = Depends(get_db)):
    job = db.get(DetectionJob, job_id)
    if not job or job.project_id != project_id:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.page_image_path:
        raise HTTPException(status_code=404, detail="Page image not ready")
    return FileResponse(job.page_image_path, media_type="image/png")


@router.get("/images/legend/{project_id}/{job_id}")
def serve_legend_image(project_id: str, job_id: str, db: Session = Depends(get_db)):
    job = db.get(DetectionJob, job_id)
    if not job or job.project_id != project_id:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.legend_crop_path:
        raise HTTPException(status_code=404, detail="Legend image not ready")
    return FileResponse(job.legend_crop_path, media_type="image/png")


@router.get("/images/result/{result_id}/matches")
def serve_matches_image(result_id: str, db: Session = Depends(get_db)):
    sr = db.get(SymbolResult, result_id)
    if not sr:
        raise HTTPException(status_code=404, detail="Result not found")
    if not sr.debug_matches_image_path:
        raise HTTPException(status_code=404, detail="Matches image not available")
    return FileResponse(sr.debug_matches_image_path, media_type="image/png")


@router.get("/images/template/{result_id}")
def serve_template_image(result_id: str, db: Session = Depends(get_db)):
    sr = db.get(SymbolResult, result_id)
    if not sr or not sr.template_path:
        raise HTTPException(status_code=404, detail="Template not found")
    return FileResponse(sr.template_path, media_type="image/png")


# ────────────────────────────────────────────────────────────
# Legend entries
# ────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/legend", response_model=list[LegendEntryOut])
def get_legend_entries(project_id: str, db: Session = Depends(get_db)):
    return (
        db.query(LegendEntry)
        .filter(LegendEntry.project_id == project_id)
        .all()
    )


@router.patch("/legend/{entry_id}", response_model=LegendEntryOut)
def update_legend_entry(entry_id: str, body: LegendEntryUpdate, db: Session = Depends(get_db)):
    entry = db.get(LegendEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Legend entry not found")
    if body.enabled is not None:
        entry.enabled = body.enabled
    if body.symbol_name is not None:
        entry.symbol_name = body.symbol_name
    if body.detection_overrides is not None:
        entry.detection_overrides = body.detection_overrides
    db.commit()
    db.refresh(entry)
    return entry


# ────────────────────────────────────────────────────────────
# User feedback  (drives learning)
# ────────────────────────────────────────────────────────────

@router.post("/results/{result_id}/feedback", response_model=FeedbackOut, status_code=201)
def submit_feedback(
    result_id: str,
    body: FeedbackSubmit,
    db: Session = Depends(get_db),
):
    sr = db.get(SymbolResult, result_id)
    if not sr:
        raise HTTPException(status_code=404, detail="Result not found")

    # Find the search region path via the job
    job = db.get(DetectionJob, sr.job_id)
    search_region_path = job.search_region_path if job else None

    fb = record_feedback(
        db=db,
        symbol_result_id=result_id,
        bbox=body.bbox,
        decision=body.decision,
        scores={
            "combined_score": body.combined_score,
            "binary_score": body.binary_score,
            "edge_score": body.edge_score,
            "iou_score": body.iou_score,
        },
        search_region_path=search_region_path,
    )
    return fb


@router.get("/learning/stats")
def learning_stats(db: Session = Depends(get_db)):
    return get_training_stats(db)


# ────────────────────────────────────────────────────────────
# Takeoff summary
# ────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/takeoff", response_model=TakeoffSummary)
def takeoff_summary(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    results = (
        db.query(SymbolResult)
        .filter(SymbolResult.project_id == project_id)
        .all()
    )

    # Fetch all presets, keyed by slug
    presets = {p.symbol_slug: p for p in db.query(SymbolPreset).all()}

    items = []
    for sr in results:
        preset = presets.get(sr.symbol_slug)
        mat = preset.material_cost if preset else 0.0
        lab = preset.labor_cost if preset else 0.0
        mins = preset.install_minutes if preset else 0.0
        count = sr.match_count

        items.append(TakeoffSummaryItem(
            symbol_name=sr.symbol_name,
            symbol_slug=sr.symbol_slug,
            match_count=count,
            material_cost=mat,
            labor_cost=lab,
            install_minutes=mins,
            total_cost=round((mat + lab) * count, 2),
            total_hours=round((mins / 60) * count, 2),
        ))

    grand_total_cost = round(sum(i.total_cost for i in items), 2)
    grand_total_hours = round(sum(i.total_hours for i in items), 2)

    # Get page_index from most recent job
    job = (
        db.query(DetectionJob)
        .filter(DetectionJob.project_id == project_id)
        .order_by(DetectionJob.created_at.desc())
        .first()
    )
    page_index = job.page_index if job else 0

    return TakeoffSummary(
        project_id=project_id,
        project_name=project.name,
        page_index=page_index,
        items=items,
        grand_total_cost=grand_total_cost,
        grand_total_hours=grand_total_hours,
    )


@router.get("/projects/{project_id}/takeoff/export")
def export_takeoff_csv(project_id: str, db: Session = Depends(get_db)):
    """Export takeoff summary as a CSV download."""
    summary = takeoff_summary(project_id, db)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Symbol", "Count", "Material Cost", "Labor Cost", "Install (min)", "Total Cost", "Total Hours"])
    for item in summary.items:
        writer.writerow([
            item.symbol_name,
            item.match_count,
            f"${item.material_cost:.2f}",
            f"${item.labor_cost:.2f}",
            item.install_minutes,
            f"${item.total_cost:.2f}",
            item.total_hours,
        ])
    writer.writerow([])
    writer.writerow(["TOTAL", "", "", "", "", f"${summary.grand_total_cost:.2f}", summary.grand_total_hours])

    output.seek(0)
    filename = f"takeoff_{project_id[:8]}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
