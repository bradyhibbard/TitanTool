"""
/api/jobs  — Detection job management and status polling
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..models_db import DetectionJob, Project
from ..schemas import DetectionJobOut, StartDetectionRequest
from ..services.detection_service import run_detection_job

router = APIRouter(prefix="/api", tags=["jobs"])


def _run_in_thread(job_id: str):
    """Run detection in a separate thread with its own DB session."""
    db = SessionLocal()
    try:
        run_detection_job(job_id, db)
    finally:
        db.close()


@router.post("/projects/{project_id}/detect", response_model=DetectionJobOut, status_code=202)
def start_detection(
    project_id: str,
    body: StartDetectionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.pdf_path:
        raise HTTPException(status_code=400, detail="Upload a PDF before running detection")

    job = DetectionJob(
        id=str(uuid.uuid4()),
        project_id=project_id,
        page_index=body.page_index,
        status="pending",
    )
    db.add(job)
    project.status = "detecting"
    db.commit()
    db.refresh(job)

    # Run detection in a background thread (FastAPI BackgroundTasks is post-response)
    t = threading.Thread(target=_run_in_thread, args=(job.id,), daemon=True)
    t.start()

    return job


@router.get("/projects/{project_id}/jobs", response_model=list[DetectionJobOut])
def list_jobs(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return (
        db.query(DetectionJob)
        .filter(DetectionJob.project_id == project_id)
        .order_by(DetectionJob.created_at.desc())
        .all()
    )


@router.get("/jobs/{job_id}", response_model=DetectionJobOut)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(DetectionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
