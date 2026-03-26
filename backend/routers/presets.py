"""
/api/presets  — Symbol cost / time preset management
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models_db import SymbolPreset
from ..schemas import MessageOut, SymbolPresetOut, SymbolPresetUpsert
from takeoff.models import SymbolTemplate

router = APIRouter(prefix="/api/presets", tags=["presets"])


@router.get("", response_model=list[SymbolPresetOut])
def list_presets(db: Session = Depends(get_db)):
    return db.query(SymbolPreset).order_by(SymbolPreset.symbol_name).all()


@router.put("/{symbol_slug}", response_model=SymbolPresetOut)
def upsert_preset(symbol_slug: str, body: SymbolPresetUpsert, db: Session = Depends(get_db)):
    preset = db.query(SymbolPreset).filter(SymbolPreset.symbol_slug == symbol_slug).first()
    if preset:
        preset.symbol_name = body.symbol_name
        preset.material_cost = body.material_cost
        preset.labor_cost = body.labor_cost
        preset.install_minutes = body.install_minutes
        preset.notes = body.notes
    else:
        preset = SymbolPreset(
            id=str(uuid.uuid4()),
            symbol_slug=symbol_slug,
            symbol_name=body.symbol_name,
            material_cost=body.material_cost,
            labor_cost=body.labor_cost,
            install_minutes=body.install_minutes,
            notes=body.notes,
        )
        db.add(preset)
    db.commit()
    db.refresh(preset)
    return preset


@router.delete("/{symbol_slug}", response_model=MessageOut)
def delete_preset(symbol_slug: str, db: Session = Depends(get_db)):
    preset = db.query(SymbolPreset).filter(SymbolPreset.symbol_slug == symbol_slug).first()
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    db.delete(preset)
    db.commit()
    return {"message": "Preset deleted"}
