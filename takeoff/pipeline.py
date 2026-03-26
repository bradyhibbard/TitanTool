import json
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw

from .pdf_utils import render_pdf_page
from .openai_utils import ask_model_for_json
from .image_utils import (
    normalized_bbox_to_pixels,
    expand_bbox,
    crop_image,
    manually_crop_symbol,
    build_search_region_image,
    save_detected_symbols,
)
from .preprocess import save_preprocessed_debug
from .detection import detect_symbol_candidates
from .review_ui import triage_candidates_for_review, review_uncertain_candidates
from .scoring import dedupe_reviewed_matches
from .prompts import LEGEND_PROMPT, PLAN_REGION_PROMPT
from .models import SymbolTemplate


def save_debug_matches(image_path, matches, out_path):
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    for i, m in enumerate(matches, start=1):
        x1, y1, x2, y2 = m["bbox"]
        label = (
            f'{i}:'
            f'c={m["combined_score"]:.2f} '
            f'b={m["binary_score"]:.2f} '
            f'e={m["edge_score"]:.2f} '
            f'i={m["iou_score"]:.2f}'
        )
        draw.rectangle([x1, y1, x2, y2], outline=(255, 0, 0), width=2)
        draw.text((x1, max(0, y1 - 14)), label, fill=(255, 0, 0))

    img.save(out_path)
    return out_path


# ============================================================
# Shared page preparation
# ============================================================

def prepare_page_shared_assets(client, config):
    """
    Prepare the shared page-level assets one time.

    These assets are shared across all symbols for the page:
    - rendered page image
    - legend crop
    - search region
    - page-level bounding boxes

    This is important for the future multi-symbol architecture,
    where we do NOT want to rerender or re-ask OpenAI for every symbol.
    """
    config.output_root_dir.mkdir(exist_ok=True)
    config.output_dir.mkdir(exist_ok=True)
    config.page_dir.mkdir(exist_ok=True)
    config.symbol_library_dir.mkdir(exist_ok=True)

    render_pdf_page(config.pdf_path, config.page_index, config.page_img_path, zoom=config.render_zoom)
    print(f"Saved rendered page to: {config.page_img_path}")

    page_img = Image.open(config.page_img_path)
    page_w, page_h = page_img.size

    legend_data = ask_model_for_json(client, config.page_img_path, LEGEND_PROMPT, model=config.model_name)
    if not legend_data.get("found", False):
        raise RuntimeError("Electrical legend was not found.")

    legend_bbox_px = normalized_bbox_to_pixels(
        legend_data["bbox_0_to_999"], page_w, page_h
    )
    legend_bbox_px = expand_bbox(*legend_bbox_px, page_w, page_h, pad=config.legend_expand_pad)

    crop_image(config.page_img_path, legend_bbox_px, config.legend_crop_path)
    print(f"Saved legend crop to: {config.legend_crop_path}")
    print(f"Legend pixel bbox on page: {legend_bbox_px}")

    plan_data = ask_model_for_json(client, config.page_img_path, PLAN_REGION_PROMPT, model=config.model_name)
    if not plan_data.get("found", False):
        raise RuntimeError("Main house plan region was not found.")

    plan_bbox_px = normalized_bbox_to_pixels(
        plan_data["bbox_0_to_999"], page_w, page_h
    )
    plan_bbox_px = expand_bbox(*plan_bbox_px, page_w, page_h, pad=config.plan_expand_pad)

    print(f"Plan search region pixel bbox on page: {plan_bbox_px}")

    build_search_region_image(config.page_img_path, plan_bbox_px, legend_bbox_px, config.search_region_path)
    print(f"Saved search-region image to: {config.search_region_path}")

    save_preprocessed_debug(
        config.search_region_path,
        config.preproc_search_binary_path,
        config.preproc_search_edges_path
    )

    return {
        "page_width": page_w,
        "page_height": page_h,
        "legend_bbox_px": legend_bbox_px,
        "plan_bbox_px": plan_bbox_px,
        "page_image_path": config.page_img_path,
        "legend_crop_path": config.legend_crop_path,
        "search_region_path": config.search_region_path,
    }


# ============================================================
# Symbol template preparation
# ============================================================

def ensure_symbol_template_paths(symbol: SymbolTemplate, config) -> SymbolTemplate:
    """
    Ensure a symbol has the expected library/template paths populated.
    """
    if symbol.template_path is None:
        symbol.template_path = config.get_library_symbol_template_path(symbol)

    if symbol.legend_row_path is None:
        symbol.legend_row_path = config.get_library_symbol_legend_row_path(symbol)

    if symbol.label_crop_path is None:
        symbol.label_crop_path = config.get_library_symbol_label_crop_path(symbol)

    return symbol


def capture_symbol_template_from_legend(symbol: SymbolTemplate, config, legend_bbox_px):
    """
    Current human-in-the-loop template creation step.

    For now:
    - user manually crops symbol from full legend crop
    - template is saved into symbol library folder
    - symbol metadata is updated

    Later this function can be extended to:
    - automatically isolate legend rows
    - auto-extract symbol area
    - OCR the label
    """
    ensure_symbol_template_paths(symbol, config)
    config.ensure_symbol_dirs(symbol)

    manual_symbol_bbox = manually_crop_symbol(
        config.legend_crop_path,
        symbol.template_path,
        symbol_name=symbol.name,
        border_px=config.manual_template_border_px
    )

    symbol.source_page_index = config.page_index
    symbol.source_legend_bbox_on_page = legend_bbox_px
    symbol.manual_symbol_bbox_within_legend = manual_symbol_bbox

    return manual_symbol_bbox


# ============================================================
# One-symbol pipeline using SymbolTemplate
# ============================================================

def run_symbol_detection_for_page(client, config, symbol: SymbolTemplate, shared_page_assets: Optional[dict] = None):
    """
    Run detection for one symbol on one page.

    This is the future-facing function that works with SymbolTemplate.
    It supports shared page assets so later multiple symbols can reuse:
    - rendered page
    - legend crop
    - search region
    """
    ensure_symbol_template_paths(symbol, config)
    config.ensure_symbol_dirs(symbol)

    if shared_page_assets is None:
        shared_page_assets = prepare_page_shared_assets(client, config)

    legend_bbox_px = shared_page_assets["legend_bbox_px"]
    plan_bbox_px = shared_page_assets["plan_bbox_px"]

    # Current workflow: manual template crop if no template exists yet
    if symbol.template_path is None or not Path(symbol.template_path).exists():
        manual_symbol_bbox = capture_symbol_template_from_legend(symbol, config, legend_bbox_px)
    else:
        manual_symbol_bbox = symbol.manual_symbol_bbox_within_legend

    page_symbol_dir = config.get_page_symbol_dir(symbol)
    candidate_debug_dir = config.get_symbol_candidate_debug_dir(symbol)
    detected_symbol_dir = config.get_symbol_detected_dir(symbol)
    debug_matches_path = config.get_symbol_debug_matches_path(symbol)
    result_json_path = config.get_symbol_result_json_path(symbol)
    preproc_template_binary_path = config.get_symbol_preproc_template_binary_path(symbol)
    preproc_template_edges_path = config.get_symbol_preproc_template_edges_path(symbol)

    save_preprocessed_debug(
        symbol.template_path,
        preproc_template_binary_path,
        preproc_template_edges_path
    )

    detection = detect_symbol_candidates(
        config.search_region_path,
        symbol.template_path,
        config,
        symbol=symbol
    )

    initial_matches = detection["initial_matches"]

    if config.enable_user_review:
        auto_accept, auto_reject, uncertain = triage_candidates_for_review(initial_matches, config)

        uncertain.sort(key=lambda c: abs(c["combined_score"] - config.auto_accept_score))
        uncertain = uncertain[:config.max_uncertain_to_review]

        print(f"\nSymbol: {symbol.name}")
        print(f"Auto-accepted: {len(auto_accept)}")
        print(f"Auto-rejected: {len(auto_reject)}")
        print(f"Needs review:  {len(uncertain)}")

        reviewed_accept, reviewed_reject, review_stopped = review_uncertain_candidates(
            symbol.template_path,
            config.search_region_path,
            uncertain,
            symbol_name=symbol.name,
            config=config
        )

        matches = auto_accept + reviewed_accept
        matches = dedupe_reviewed_matches(matches, overlap_thresh=config.nms_overlap_thresh)

        review_summary = {
            "auto_accepted_count": len(auto_accept),
            "auto_rejected_count": len(auto_reject),
            "uncertain_count": len(uncertain),
            "user_accepted_count": len(reviewed_accept),
            "user_rejected_count": len(reviewed_reject),
            "review_stopped_early": review_stopped
        }
    else:
        matches = initial_matches
        review_summary = {
            "auto_accepted_count": len(matches),
            "auto_rejected_count": 0,
            "uncertain_count": 0,
            "user_accepted_count": 0,
            "user_rejected_count": 0,
            "review_stopped_early": False
        }

    save_debug_matches(config.search_region_path, matches, debug_matches_path)
    print(f"Saved debug match image to: {debug_matches_path}")

    detected_symbol_files = save_detected_symbols(
        config.search_region_path,
        matches,
        symbol.name,
        detected_symbol_dir
    )
    print(f"Saved {len(detected_symbol_files)} detected symbol crops to: {detected_symbol_dir}")

    result = {
        "page_index": config.page_index,
        "page_number": config.page_index + 1,
        "symbol_name": symbol.name,
        "symbol_slug": symbol.slug,
        "legend_bbox_px_on_page": legend_bbox_px,
        "plan_bbox_px_on_page": plan_bbox_px,
        "manual_symbol_bbox_within_legend": manual_symbol_bbox,
        "match_count_inside_plan_outside_legend": len(matches),
        "proposal_count": detection["proposal_count"],
        "template_size": detection["template_size"],
        "review_summary": review_summary,
        "detected_symbol_images": detected_symbol_files,
        "matches": matches,
        "top_scored_candidates_preview": detection["all_scored_candidates"][:20],
        "parameters": {
            "render_zoom": config.render_zoom,
            "manual_template_border_px": config.manual_template_border_px,
            "proposal_scales": config.proposal_scales,
            "final_scales": config.final_scales,
            "edge_proposal_threshold": config.edge_proposal_threshold,
            "max_edge_proposals_per_scale": config.max_edge_proposals_per_scale,
            "final_accept_score": config.final_accept_score,
            "final_min_binary_score": config.final_min_binary_score,
            "final_min_edge_score": config.final_min_edge_score,
            "final_min_iou_score": config.final_min_iou_score,
            "min_center_distance_factor": config.min_center_distance_factor,
            "nms_overlap_thresh": config.nms_overlap_thresh,
            "enable_user_review": config.enable_user_review,
            "auto_accept_score": config.auto_accept_score,
            "auto_reject_score": config.auto_reject_score,
            "review_iou_floor": config.review_iou_floor,
            "max_uncertain_to_review": config.max_uncertain_to_review
        },
        "files": {
            "page_image": str(config.page_img_path),
            "legend_crop": str(config.legend_crop_path),
            "symbol_crop": str(symbol.template_path),
            "search_region_image": str(config.search_region_path),
            "debug_matches": str(debug_matches_path),
            "preprocessed_template_binary": str(preproc_template_binary_path),
            "preprocessed_template_edges": str(preproc_template_edges_path),
            "preprocessed_search_binary": str(config.preproc_search_binary_path),
            "preprocessed_search_edges": str(config.preproc_search_edges_path),
            "grouped_mask": str(config.debug_grouped_mask_path),
            "candidate_proposals_overlay": str(config.debug_proposals_path),
            "candidate_debug_dir": str(candidate_debug_dir),
            "detected_symbol_dir": str(detected_symbol_dir),
            "page_symbol_dir": str(page_symbol_dir),
        },
        "symbol_template": symbol.to_dict(),
    }

    with open(result_json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print("\n========== RESULT ==========")
    print(f"Counted symbol: {symbol.name}")
    print(f"{symbol.name} count on page {config.page_index + 1} inside main plan and outside legend: {len(matches)}")
    print(f"Proposal count: {detection['proposal_count']}")
    print(f"Saved result JSON to: {result_json_path}")
    print("============================\n")

    return result


# ============================================================
# Backward-compatible wrapper
# ============================================================

def run_single_symbol_page_pipeline(client, config):
    """
    Backward-compatible wrapper so your existing main.py can still work.

    Internally, this now creates a SymbolTemplate object and routes
    through the new symbol-based architecture.
    """
    symbol = SymbolTemplate.from_name(config.symbol_name)
    shared_page_assets = prepare_page_shared_assets(client, config)
    return run_symbol_detection_for_page(
        client=client,
        config=config,
        symbol=symbol,
        shared_page_assets=shared_page_assets
    )