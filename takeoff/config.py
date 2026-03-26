from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from .models import SymbolTemplate


@dataclass
class AppConfig:
    pdf_path: str = "house_plans.pdf"
    page_index: int = 4
    model_name: str = "gpt-5.4"

    # Temporary compatibility field for current single-symbol flow.
    # Later this will be replaced by SymbolTemplate objects from SymbolLibrary.
    symbol_name: str = "Bath Fan"

    # Root output folder for all runs
    output_root_dir: Path = Path("output")

    # Optional logical name for the current plan set/job
    plan_name: str = "default_plan"

    render_zoom: float = 2.0
    manual_template_border_px: int = 6

    proposal_scales: tuple = (0.85, 0.95, 1.0, 1.05, 1.15)
    final_scales: tuple = (0.90, 1.00, 1.10)
    edge_proposal_threshold: float = 0.32
    max_edge_proposals_per_scale: int = 60

    final_accept_score: float = 0.50
    final_min_binary_score: float = 0.20
    final_min_edge_score: float = 0.10
    final_min_iou_score: float = 0.12
    min_center_distance_factor: float = 0.45
    nms_overlap_thresh: float = 0.20

    enable_user_review: bool = True
    auto_accept_score: float = 0.72
    auto_reject_score: float = 0.38
    review_iou_floor: float = 0.08
    max_uncertain_to_review: int = 20

    save_top_candidate_crops: int = 30
    review_window_name: str = "Symbol Review"

    legend_expand_pad: int = 125
    plan_expand_pad: int = 10

    # ============================================================
    # Core path helpers
    # ============================================================

    @property
    def output_dir(self) -> Path:
        """
        Main output directory for the active plan set.
        """
        return self.output_root_dir / self.plan_name

    @property
    def page_dir(self) -> Path:
        """
        Shared outputs for the current page.
        """
        return self.output_dir / f"page_{self.page_index + 1}"

    @property
    def symbol_library_dir(self) -> Path:
        """
        Plan-set-level symbol library folder.
        """
        return self.output_dir / "symbol_library"

    @property
    def symbol_library_json_path(self) -> Path:
        return self.symbol_library_dir / "symbols.json"

    @property
    def page_img_path(self) -> Path:
        return self.page_dir / f"page_{self.page_index + 1}.png"

    @property
    def legend_crop_path(self) -> Path:
        return self.page_dir / "electrical_legend_crop.png"

    @property
    def search_region_path(self) -> Path:
        return self.page_dir / f"page_{self.page_index + 1}_search_region.png"

    @property
    def preproc_search_binary_path(self) -> Path:
        return self.page_dir / "debug_search_binary.png"

    @property
    def preproc_search_edges_path(self) -> Path:
        return self.page_dir / "debug_search_edges.png"

    @property
    def debug_grouped_mask_path(self) -> Path:
        return self.page_dir / "debug_grouped_mask.png"

    @property
    def debug_proposals_path(self) -> Path:
        return self.page_dir / "debug_candidate_proposals.png"

    # ============================================================
    # Backward-compatible single-symbol helpers
    # ============================================================

    @property
    def symbol_slug(self) -> str:
        return (
            self.symbol_name.strip()
            .lower()
            .replace("&", "and")
            .replace("/", "_")
            .replace("\\", "_")
            .replace(" ", "_")
        )

    @property
    def symbol_dir(self) -> Path:
        """
        Current symbol-specific output folder for the current page.
        This keeps outputs separated by symbol, which is important for
        multi-symbol architecture.
        """
        return self.page_dir / self.symbol_slug

    @property
    def candidate_debug_dir(self) -> Path:
        return self.symbol_dir / "candidate_debug"

    @property
    def detected_symbol_dir(self) -> Path:
        return self.symbol_dir / "detected_symbols"

    @property
    def symbol_crop_path(self) -> Path:
        return self.symbol_dir / f"{self.symbol_slug}_symbol_crop.png"

    @property
    def debug_matches_path(self) -> Path:
        return self.symbol_dir / f"page_{self.page_index + 1}_{self.symbol_slug}_matches.png"

    @property
    def result_json_path(self) -> Path:
        return self.symbol_dir / f"page_{self.page_index + 1}_{self.symbol_slug}_count.json"

    @property
    def preproc_template_binary_path(self) -> Path:
        return self.symbol_dir / "debug_template_binary.png"

    @property
    def preproc_template_edges_path(self) -> Path:
        return self.symbol_dir / "debug_template_edges.png"

    # ============================================================
    # SymbolTemplate-aware helpers
    # ============================================================

    def get_symbol_slug(self, symbol: SymbolTemplate) -> str:
        return symbol.slug

    def get_page_symbol_dir(self, symbol: SymbolTemplate) -> Path:
        return self.page_dir / symbol.slug

    def get_symbol_candidate_debug_dir(self, symbol: SymbolTemplate) -> Path:
        return self.get_page_symbol_dir(symbol) / "candidate_debug"

    def get_symbol_detected_dir(self, symbol: SymbolTemplate) -> Path:
        return self.get_page_symbol_dir(symbol) / "detected_symbols"

    def get_symbol_crop_path(self, symbol: SymbolTemplate) -> Path:
        return self.get_page_symbol_dir(symbol) / f"{symbol.slug}_symbol_crop.png"

    def get_symbol_debug_matches_path(self, symbol: SymbolTemplate) -> Path:
        return self.get_page_symbol_dir(symbol) / f"page_{self.page_index + 1}_{symbol.slug}_matches.png"

    def get_symbol_result_json_path(self, symbol: SymbolTemplate) -> Path:
        return self.get_page_symbol_dir(symbol) / f"page_{self.page_index + 1}_{symbol.slug}_count.json"

    def get_symbol_preproc_template_binary_path(self, symbol: SymbolTemplate) -> Path:
        return self.get_page_symbol_dir(symbol) / "debug_template_binary.png"

    def get_symbol_preproc_template_edges_path(self, symbol: SymbolTemplate) -> Path:
        return self.get_page_symbol_dir(symbol) / "debug_template_edges.png"

    def get_library_symbol_dir(self, symbol: SymbolTemplate) -> Path:
        return self.symbol_library_dir / symbol.slug

    def get_library_symbol_template_path(self, symbol: SymbolTemplate) -> Path:
        return self.get_library_symbol_dir(symbol) / "template.png"

    def get_library_symbol_legend_row_path(self, symbol: SymbolTemplate) -> Path:
        return self.get_library_symbol_dir(symbol) / "legend_row.png"

    def get_library_symbol_label_crop_path(self, symbol: SymbolTemplate) -> Path:
        return self.get_library_symbol_dir(symbol) / "label_crop.png"

    # ============================================================
    # Directory creation
    # ============================================================

    def ensure_dirs(self) -> None:
        """
        Ensures the current single-symbol-compatible folder structure exists.
        """
        self.output_root_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
        self.page_dir.mkdir(exist_ok=True)
        self.symbol_library_dir.mkdir(exist_ok=True)

        self.symbol_dir.mkdir(exist_ok=True)
        self.candidate_debug_dir.mkdir(exist_ok=True)
        self.detected_symbol_dir.mkdir(exist_ok=True)

    def ensure_symbol_dirs(self, symbol: SymbolTemplate) -> None:
        """
        Ensures per-symbol folders exist for a specific symbol object.
        """
        self.output_root_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
        self.page_dir.mkdir(exist_ok=True)
        self.symbol_library_dir.mkdir(exist_ok=True)

        self.get_page_symbol_dir(symbol).mkdir(exist_ok=True)
        self.get_symbol_candidate_debug_dir(symbol).mkdir(exist_ok=True)
        self.get_symbol_detected_dir(symbol).mkdir(exist_ok=True)

        self.get_library_symbol_dir(symbol).mkdir(exist_ok=True)