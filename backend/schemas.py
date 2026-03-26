"""
Pydantic schemas for request / response validation.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict


# ────────────────────────────────────────────────────────────
# Projects
# ────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    pdf_filename: str | None
    page_count: int
    status: str
    created_at: datetime
    updated_at: datetime


# ────────────────────────────────────────────────────────────
# Symbol presets
# ────────────────────────────────────────────────────────────

class SymbolPresetUpsert(BaseModel):
    symbol_name: str
    material_cost: float = 0.0
    labor_cost: float = 0.0
    install_minutes: float = 0.0
    notes: str = ""


class SymbolPresetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    symbol_slug: str
    symbol_name: str
    material_cost: float
    labor_cost: float
    install_minutes: float
    notes: str
    updated_at: datetime


# ────────────────────────────────────────────────────────────
# Detection jobs
# ────────────────────────────────────────────────────────────

class StartDetectionRequest(BaseModel):
    page_index: int = 0
    # Slugs to detect — if empty, detects all legend entries
    symbol_slugs: list[str] = []
    # Optionally skip user review (auto-accept all)
    skip_review: bool = True


class DetectionJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    page_index: int
    status: str
    error_message: str | None
    page_image_path: str | None
    legend_crop_path: str | None
    legend_bbox: dict | None
    plan_bbox: dict | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


# ────────────────────────────────────────────────────────────
# Symbol results
# ────────────────────────────────────────────────────────────

class SymbolResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    project_id: str
    symbol_name: str
    symbol_slug: str
    template_path: str | None
    matches: list[Any]
    match_count: int
    debug_matches_image_path: str | None
    created_at: datetime


class TakeoffSummaryItem(BaseModel):
    symbol_name: str
    symbol_slug: str
    match_count: int
    material_cost: float
    labor_cost: float
    install_minutes: float
    total_cost: float
    total_hours: float


class TakeoffSummary(BaseModel):
    project_id: str
    project_name: str
    page_index: int
    items: list[TakeoffSummaryItem]
    grand_total_cost: float
    grand_total_hours: float


# ────────────────────────────────────────────────────────────
# Feedback
# ────────────────────────────────────────────────────────────

class FeedbackSubmit(BaseModel):
    bbox: list[int]                          # [x1, y1, x2, y2]
    decision: str                            # "accept" | "reject"
    combined_score: float = 0.0
    binary_score: float = 0.0
    edge_score: float = 0.0
    iou_score: float = 0.0


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    symbol_result_id: str
    symbol_slug: str
    bbox: list[Any]
    combined_score: float
    decision: str
    created_at: datetime


# ────────────────────────────────────────────────────────────
# Legend entries
# ────────────────────────────────────────────────────────────

class LegendEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    job_id: str
    symbol_name: str
    symbol_slug: str
    icon_bbox_in_legend: list | None
    template_path: str | None
    enabled: bool
    detection_overrides: dict


class LegendEntryUpdate(BaseModel):
    enabled: bool | None = None
    symbol_name: str | None = None
    detection_overrides: dict | None = None


# ────────────────────────────────────────────────────────────
# Misc
# ────────────────────────────────────────────────────────────

class MessageOut(BaseModel):
    message: str
