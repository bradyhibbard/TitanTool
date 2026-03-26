from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional


BBox = Tuple[int, int, int, int]


# ============================================================
# Detection models
# ============================================================

@dataclass
class DetectionCandidate:
    bbox: BBox
    combined_score: float
    binary_score: float
    edge_score: float
    iou_score: float
    density_score: float
    contour_score: float
    candidate_density: float
    template_density: float
    candidate_contours: int
    template_contours: int
    proposal_source: str = ""
    proposal_scale: float = 1.0
    proposal_score: float = 0.0
    decision_source: str = ""
    user_review: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bbox": list(self.bbox),
            "combined_score": self.combined_score,
            "binary_score": self.binary_score,
            "edge_score": self.edge_score,
            "iou_score": self.iou_score,
            "density_score": self.density_score,
            "contour_score": self.contour_score,
            "candidate_density": self.candidate_density,
            "template_density": self.template_density,
            "candidate_contours": self.candidate_contours,
            "template_contours": self.template_contours,
            "proposal_source": self.proposal_source,
            "proposal_scale": self.proposal_scale,
            "proposal_score": self.proposal_score,
            "decision_source": self.decision_source,
            "user_review": self.user_review,
        }


@dataclass
class DetectionResult:
    initial_matches: List[dict]
    all_scored_candidates: List[dict]
    proposal_count: int
    template_size: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "initial_matches": self.initial_matches,
            "all_scored_candidates": self.all_scored_candidates,
            "proposal_count": self.proposal_count,
            "template_size": self.template_size,
        }


# ============================================================
# Symbol library models
# ============================================================

@dataclass
class SymbolTemplate:
    """
    Represents one symbol template for one plan set.

    This can start as a manually cropped symbol from the legend,
    and later evolve into an automatically extracted legend entry.
    """
    name: str
    slug: str

    template_path: Optional[Path] = None
    legend_row_path: Optional[Path] = None
    label_crop_path: Optional[Path] = None

    source_page_index: Optional[int] = None
    source_legend_bbox_on_page: Optional[BBox] = None
    manual_symbol_bbox_within_legend: Optional[BBox] = None

    label_text: Optional[str] = None
    description: Optional[str] = None

    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def make_slug(name: str) -> str:
        return (
            name.strip()
            .lower()
            .replace("&", "and")
            .replace("/", "_")
            .replace("\\", "_")
            .replace(" ", "_")
        )

    @classmethod
    def from_name(cls, name: str) -> "SymbolTemplate":
        return cls(
            name=name,
            slug=cls.make_slug(name),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "slug": self.slug,
            "template_path": str(self.template_path) if self.template_path else None,
            "legend_row_path": str(self.legend_row_path) if self.legend_row_path else None,
            "label_crop_path": str(self.label_crop_path) if self.label_crop_path else None,
            "source_page_index": self.source_page_index,
            "source_legend_bbox_on_page": list(self.source_legend_bbox_on_page) if self.source_legend_bbox_on_page else None,
            "manual_symbol_bbox_within_legend": list(self.manual_symbol_bbox_within_legend) if self.manual_symbol_bbox_within_legend else None,
            "label_text": self.label_text,
            "description": self.description,
            "enabled": self.enabled,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SymbolTemplate":
        return cls(
            name=data["name"],
            slug=data["slug"],
            template_path=Path(data["template_path"]) if data.get("template_path") else None,
            legend_row_path=Path(data["legend_row_path"]) if data.get("legend_row_path") else None,
            label_crop_path=Path(data["label_crop_path"]) if data.get("label_crop_path") else None,
            source_page_index=data.get("source_page_index"),
            source_legend_bbox_on_page=tuple(data["source_legend_bbox_on_page"]) if data.get("source_legend_bbox_on_page") else None,
            manual_symbol_bbox_within_legend=tuple(data["manual_symbol_bbox_within_legend"]) if data.get("manual_symbol_bbox_within_legend") else None,
            label_text=data.get("label_text"),
            description=data.get("description"),
            enabled=data.get("enabled", True),
            metadata=data.get("metadata", {}),
        )


@dataclass
class SymbolLibrary:
    """
    Represents the symbol library for one plan set.
    """
    plan_name: str
    symbols: List[SymbolTemplate] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_symbol(self, symbol: SymbolTemplate) -> None:
        existing = self.get_symbol_by_slug(symbol.slug)
        if existing is not None:
            raise ValueError(f"Symbol with slug '{symbol.slug}' already exists in library.")
        self.symbols.append(symbol)

    def get_symbol_by_slug(self, slug: str) -> Optional[SymbolTemplate]:
        for symbol in self.symbols:
            if symbol.slug == slug:
                return symbol
        return None

    def get_symbol_by_name(self, name: str) -> Optional[SymbolTemplate]:
        target_slug = SymbolTemplate.make_slug(name)
        return self.get_symbol_by_slug(target_slug)

    def enabled_symbols(self) -> List[SymbolTemplate]:
        return [s for s in self.symbols if s.enabled]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_name": self.plan_name,
            "symbols": [s.to_dict() for s in self.symbols],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SymbolLibrary":
        return cls(
            plan_name=data["plan_name"],
            symbols=[SymbolTemplate.from_dict(s) for s in data.get("symbols", [])],
            metadata=data.get("metadata", {}),
        )


# ============================================================
# Future-facing result models
# ============================================================

@dataclass
class SymbolCountResult:
    symbol_name: str
    symbol_slug: str
    count: int
    matches: List[dict] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol_name": self.symbol_name,
            "symbol_slug": self.symbol_slug,
            "count": self.count,
            "matches": self.matches,
        }


@dataclass
class PageTakeoffResult:
    page_index: int
    page_number: int
    symbol_results: List[SymbolCountResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_index": self.page_index,
            "page_number": self.page_number,
            "symbol_results": [r.to_dict() for r in self.symbol_results],
        }