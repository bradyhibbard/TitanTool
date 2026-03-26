"""
SQLAlchemy ORM models for TitanTool.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    String, Integer, Float, Boolean, Text, DateTime,
    ForeignKey, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def _now():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


# ────────────────────────────────────────────────────────────
# Projects
# ────────────────────────────────────────────────────────────

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    pdf_path: Mapped[str | None] = mapped_column(String, nullable=True)
    pdf_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="created")  # created | ready | detecting | done | error
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    jobs: Mapped[list["DetectionJob"]] = relationship("DetectionJob", back_populates="project", cascade="all, delete-orphan")
    symbol_results: Mapped[list["SymbolResult"]] = relationship("SymbolResult", back_populates="project", cascade="all, delete-orphan")


# ────────────────────────────────────────────────────────────
# Symbol cost / time presets  (per-user global library)
# ────────────────────────────────────────────────────────────

class SymbolPreset(Base):
    __tablename__ = "symbol_presets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    # Canonical slug links presets to detected symbols (e.g. "bath_fan")
    symbol_slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    symbol_name: Mapped[str] = mapped_column(String, nullable=False)
    # Cost in dollars
    material_cost: Mapped[float] = mapped_column(Float, default=0.0)
    labor_cost: Mapped[float] = mapped_column(Float, default=0.0)
    # Time in minutes
    install_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


# ────────────────────────────────────────────────────────────
# Detection jobs  (one per "run" / page-set)
# ────────────────────────────────────────────────────────────

class DetectionJob(Base):
    __tablename__ = "detection_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"), nullable=False)
    page_index: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending | running | done | error
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Paths to shared page assets produced during detection
    page_image_path: Mapped[str | None] = mapped_column(String, nullable=True)
    legend_crop_path: Mapped[str | None] = mapped_column(String, nullable=True)
    search_region_path: Mapped[str | None] = mapped_column(String, nullable=True)
    legend_bbox: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # {x1,y1,x2,y2}
    plan_bbox: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    project: Mapped["Project"] = relationship("Project", back_populates="jobs")
    symbol_results: Mapped[list["SymbolResult"]] = relationship("SymbolResult", back_populates="job", cascade="all, delete-orphan")


# ────────────────────────────────────────────────────────────
# Per-symbol detection results
# ────────────────────────────────────────────────────────────

class SymbolResult(Base):
    __tablename__ = "symbol_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String, ForeignKey("detection_jobs.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"), nullable=False)
    symbol_name: Mapped[str] = mapped_column(String, nullable=False)
    symbol_slug: Mapped[str] = mapped_column(String, nullable=False)
    template_path: Mapped[str | None] = mapped_column(String, nullable=True)
    # Bounding boxes for all accepted matches — stored as JSON list
    matches: Mapped[list] = mapped_column(JSON, default=list)
    match_count: Mapped[int] = mapped_column(Integer, default=0)
    # Overlays / debug images
    debug_matches_image_path: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    job: Mapped["DetectionJob"] = relationship("DetectionJob", back_populates="symbol_results")
    project: Mapped["Project"] = relationship("Project", back_populates="symbol_results")
    feedback: Mapped[list["DetectionFeedback"]] = relationship("DetectionFeedback", back_populates="symbol_result", cascade="all, delete-orphan")


# ────────────────────────────────────────────────────────────
# User feedback on individual detections  (powers learning)
# ────────────────────────────────────────────────────────────

class DetectionFeedback(Base):
    __tablename__ = "detection_feedback"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    symbol_result_id: Mapped[str] = mapped_column(String, ForeignKey("symbol_results.id"), nullable=False)
    symbol_slug: Mapped[str] = mapped_column(String, nullable=False)
    # The specific candidate bbox being reviewed
    bbox: Mapped[list] = mapped_column(JSON, nullable=False)               # [x1, y1, x2, y2]
    # Scores at detection time
    combined_score: Mapped[float] = mapped_column(Float, default=0.0)
    binary_score: Mapped[float] = mapped_column(Float, default=0.0)
    edge_score: Mapped[float] = mapped_column(Float, default=0.0)
    iou_score: Mapped[float] = mapped_column(Float, default=0.0)
    # User decision
    decision: Mapped[str] = mapped_column(String, nullable=False)          # "accept" | "reject"
    # Path to the cropped image of this detection (for ML training)
    crop_image_path: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    symbol_result: Mapped["SymbolResult"] = relationship("SymbolResult", back_populates="feedback")


# ────────────────────────────────────────────────────────────
# Legend symbol entries  (auto-extracted from legend)
# ────────────────────────────────────────────────────────────

class LegendEntry(Base):
    __tablename__ = "legend_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"), nullable=False)
    job_id: Mapped[str] = mapped_column(String, ForeignKey("detection_jobs.id"), nullable=False)
    symbol_name: Mapped[str] = mapped_column(String, nullable=False)
    symbol_slug: Mapped[str] = mapped_column(String, nullable=False)
    # Bounding box of the symbol icon inside the legend crop image
    icon_bbox_in_legend: Mapped[list | None] = mapped_column(JSON, nullable=True)
    template_path: Mapped[str | None] = mapped_column(String, nullable=True)
    # Whether to detect this symbol in the plan
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Overrides for detection tuning
    detection_overrides: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
