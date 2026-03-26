"""
/api/projects  — CRUD + PDF upload
"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import fitz  # PyMuPDF
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..models_db import Project
from ..schemas import MessageOut, ProjectCreate, ProjectOut

router = APIRouter(prefix="/api/projects", tags=["projects"])

UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(
        id=str(uuid.uuid4()),
        name=body.name,
        description=body.description,
        status="created",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).order_by(Project.created_at.desc()).all()


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}", response_model=MessageOut)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return {"message": "Project deleted"}


@router.post("/{project_id}/upload", response_model=ProjectOut)
async def upload_pdf(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    project_upload_dir = UPLOADS_DIR / project_id
    project_upload_dir.mkdir(parents=True, exist_ok=True)

    dest = project_upload_dir / "plan.pdf"
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Count pages
    try:
        doc = fitz.open(str(dest))
        page_count = doc.page_count
        doc.close()
    except Exception:
        page_count = 0

    project.pdf_path = str(dest)
    project.pdf_filename = file.filename
    project.page_count = page_count
    project.status = "ready"
    db.commit()
    db.refresh(project)
    return project
