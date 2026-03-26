import cv2
import numpy as np

from .preprocess import preprocess_variants
from .proposals import (
    generate_contour_proposals,
    generate_edge_match_proposals,
    dedupe_proposals,
)
from .scoring import score_candidate, filter_and_dedupe_initial_matches
from .image_utils import draw_boxes, save_candidate_crop


def rotate_image_90_multiples(img, angle):
    """
    Rotate image by 0/90/180/270 degrees.
    """
    normalized = angle % 360

    if normalized == 0:
        return img.copy()
    if normalized == 90:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    if normalized == 180:
        return cv2.rotate(img, cv2.ROTATE_180)
    if normalized == 270:
        return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)

    raise ValueError(f"Only 0/90/180/270 rotations are supported, got: {angle}")


def get_symbol_detection_settings(config, symbol=None):
    """
    Build effective detection settings for a symbol.

    Defaults come from config.
    Optional symbol-specific overrides come from:
        symbol.metadata["detection_overrides"]
    """
    settings = {
        "proposal_scales": config.proposal_scales,
        "final_scales": config.final_scales,
        "edge_proposal_threshold": config.edge_proposal_threshold,
        "max_edge_proposals_per_scale": config.max_edge_proposals_per_scale,
        "save_top_candidate_crops": config.save_top_candidate_crops,
        "proposal_dedupe_overlap_thresh": 0.25,
        "template_rotations": [0],
    }

    if symbol is not None:
        overrides = symbol.metadata.get("detection_overrides", {})
        if overrides:
            settings.update(overrides)

    return settings


def detect_symbol_candidates(search_region_path, template_path, config, symbol=None):
    search_bgr = cv2.imread(str(search_region_path))
    template_bgr = cv2.imread(str(template_path))

    if search_bgr is None:
        raise RuntimeError(f"Could not read search region image: {search_region_path}")
    if template_bgr is None:
        raise RuntimeError(f"Could not read template image: {template_path}")

    settings = get_symbol_detection_settings(config, symbol=symbol)

    search_proc = preprocess_variants(search_bgr)
    cv2.imwrite(str(config.debug_grouped_mask_path), search_proc["grouped"])

    all_proposals = []
    all_scored = []
    template_sizes = []

    rotations = settings["template_rotations"]
    seen_rotations = set()
    normalized_rotations = []
    for angle in rotations:
        a = int(angle) % 360
        if a not in (0, 90, 180, 270):
            continue
        if a not in seen_rotations:
            seen_rotations.add(a)
            normalized_rotations.append(a)

    if not normalized_rotations:
        normalized_rotations = [0]

    for angle in normalized_rotations:
        rotated_template_bgr = rotate_image_90_multiples(template_bgr, angle)
        template_proc = preprocess_variants(rotated_template_bgr)

        template_h, template_w = template_proc["binary"].shape[:2]
        template_sizes.append((template_w, template_h))

        contour_proposals = generate_contour_proposals(
            search_proc["grouped"],
            template_w=template_w,
            template_h=template_h,
            candidate_scales=settings["final_scales"]
        )

        edge_proposals = generate_edge_match_proposals(
            search_proc["edges"],
            template_proc["edges"],
            scales=settings["proposal_scales"],
            threshold=settings["edge_proposal_threshold"],
            max_per_scale=settings["max_edge_proposals_per_scale"]
        )

        rotated_props = contour_proposals + edge_proposals

        for prop in rotated_props:
            prop["template_rotation"] = angle

        all_proposals.extend(rotated_props)

        for prop in rotated_props:
            result = score_candidate(search_bgr, template_proc, prop["bbox"])
            if result is None:
                continue

            result["proposal_source"] = prop["source"]
            result["proposal_scale"] = prop["scale"]
            result["proposal_score"] = float(prop["proposal_score"])
            result["template_rotation"] = angle
            all_scored.append(result)

    all_proposals = dedupe_proposals(
        all_proposals,
        overlap_thresh=settings["proposal_dedupe_overlap_thresh"]
    )

    proposal_boxes = [p["bbox"] for p in all_proposals]
    proposal_labels = [
        f'{p["source"]}:{round(p["proposal_score"], 2)} r{p.get("template_rotation", 0)}'
        for p in all_proposals
    ]
    draw_boxes(
        search_region_path,
        proposal_boxes,
        config.debug_proposals_path,
        color=(0, 0, 255),
        labels=proposal_labels
    )

    all_scored.sort(key=lambda m: m["combined_score"], reverse=True)

    if symbol is not None:
        candidate_debug_dir = config.get_symbol_candidate_debug_dir(symbol)
    else:
        candidate_debug_dir = config.candidate_debug_dir

    for i, m in enumerate(all_scored[:settings["save_top_candidate_crops"]], start=1):
        crop_name = (
            f"{i:02d}_score_{m['combined_score']:.3f}"
            f"_bin_{m['binary_score']:.3f}"
            f"_edge_{m['edge_score']:.3f}"
            f"_iou_{m['iou_score']:.3f}"
            f"_rot_{m.get('template_rotation', 0)}.png"
        )
        save_candidate_crop(search_bgr, m["bbox"], candidate_debug_dir / crop_name)

    if template_sizes:
        max_template_w = max(w for w, h in template_sizes)
        max_template_h = max(h for w, h in template_sizes)
    else:
        max_template_w = template_bgr.shape[1]
        max_template_h = template_bgr.shape[0]

    initial_matches = filter_and_dedupe_initial_matches(
        all_scored,
        max_template_w,
        max_template_h,
        config
    )

    return {
        "initial_matches": initial_matches,
        "all_scored_candidates": all_scored,
        "proposal_count": len(all_proposals),
        "template_size": {
            "width": max_template_w,
            "height": max_template_h
        },
        "effective_settings": settings,
    }