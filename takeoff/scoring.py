import cv2
import numpy as np
from .preprocess import preprocess_variants


def non_max_suppression(boxes, scores, overlap_thresh=0.15):
    if len(boxes) == 0:
        return []

    boxes = np.array(boxes, dtype=np.float32)
    scores = np.array(scores, dtype=np.float32)

    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]

    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]

    keep = []

    while order.size > 0:
        i = order[0]
        keep.append(int(i))

        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        w = np.maximum(0, xx2 - xx1 + 1)
        h = np.maximum(0, yy2 - yy1 + 1)
        inter = w * h

        union = areas[i] + areas[order[1:]] - inter + 1e-6
        iou = inter / union

        inds = np.where(iou <= overlap_thresh)[0]
        order = order[inds + 1]

    return keep


def center_distance(box_a, box_b):
    ax = (box_a[0] + box_a[2]) / 2.0
    ay = (box_a[1] + box_a[3]) / 2.0
    bx = (box_b[0] + box_b[2]) / 2.0
    by = (box_b[1] + box_b[3]) / 2.0
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def safe_match_score(a, b, method=cv2.TM_CCOEFF_NORMED):
    if a.shape != b.shape:
        raise ValueError("safe_match_score expects equal-sized inputs")

    res = cv2.matchTemplate(a, b, method)
    val = float(res[0, 0])

    if np.isnan(val):
        val = -1.0

    return val


def mask_iou(a_bin, b_bin):
    a = (a_bin > 0).astype(np.uint8)
    b = (b_bin > 0).astype(np.uint8)

    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()

    if union == 0:
        return 0.0

    return float(inter / union)


def contour_count(bin_img):
    contours, _ = cv2.findContours(bin_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return len(contours)


def score_candidate(search_bgr, template_proc, bbox):
    x1, y1, x2, y2 = bbox
    candidate_bgr = search_bgr[y1:y2, x1:x2]

    if candidate_bgr.size == 0:
        return None

    candidate_proc = preprocess_variants(candidate_bgr)

    t_bin = template_proc["binary"]
    t_edges = template_proc["edges"]

    th, tw = t_bin.shape[:2]

    c_bin = cv2.resize(candidate_proc["binary"], (tw, th), interpolation=cv2.INTER_AREA)
    c_edges = cv2.resize(candidate_proc["edges"], (tw, th), interpolation=cv2.INTER_AREA)

    binary_score = safe_match_score(c_bin, t_bin, method=cv2.TM_CCOEFF_NORMED)

    if cv2.countNonZero(t_edges) > 0 and cv2.countNonZero(c_edges) > 0:
        edge_score = safe_match_score(c_edges, t_edges, method=cv2.TM_CCOEFF_NORMED)
    else:
        edge_score = 0.0

    iou_score = mask_iou(c_bin, t_bin)

    t_density = cv2.countNonZero(t_bin) / max(tw * th, 1)
    c_density = cv2.countNonZero(c_bin) / max(tw * th, 1)
    density_diff = abs(c_density - t_density)
    density_score = max(0.0, 1.0 - min(1.0, density_diff / 0.25))

    t_cc = contour_count(t_bin)
    c_cc = contour_count(c_bin)
    cc_diff = abs(c_cc - t_cc)
    contour_score = max(0.0, 1.0 - min(1.0, cc_diff / max(3, t_cc, 1)))

    combined = (
        0.38 * binary_score +
        0.28 * edge_score +
        0.20 * iou_score +
        0.08 * density_score +
        0.06 * contour_score
    )

    return {
        "bbox": [int(x1), int(y1), int(x2), int(y2)],
        "combined_score": float(combined),
        "binary_score": float(binary_score),
        "edge_score": float(edge_score),
        "iou_score": float(iou_score),
        "density_score": float(density_score),
        "contour_score": float(contour_score),
        "candidate_density": float(c_density),
        "template_density": float(t_density),
        "candidate_contours": int(c_cc),
        "template_contours": int(t_cc),
    }


def filter_and_dedupe_initial_matches(scored_matches, template_w, template_h, config):
    if not scored_matches:
        return []

    kept = []
    for m in scored_matches:
        if m["combined_score"] < config.final_accept_score:
            continue
        if m["binary_score"] < config.final_min_binary_score:
            continue
        if m["edge_score"] < config.final_min_edge_score:
            continue
        if m["iou_score"] < config.final_min_iou_score:
            continue
        kept.append(m)

    if not kept:
        return []

    kept.sort(key=lambda m: m["combined_score"], reverse=True)

    min_center_distance = max(
        12,
        int(round(max(template_w, template_h) * config.min_center_distance_factor))
    )
    center_kept = []

    for m in kept:
        too_close = False
        for k in center_kept:
            if center_distance(m["bbox"], k["bbox"]) < min_center_distance:
                too_close = True
                break
        if not too_close:
            center_kept.append(m)

    if not center_kept:
        return []

    boxes = [m["bbox"] for m in center_kept]
    scores = [m["combined_score"] for m in center_kept]
    keep_idx = non_max_suppression(boxes, scores, overlap_thresh=config.nms_overlap_thresh)

    final_matches = [center_kept[i] for i in keep_idx]
    final_matches.sort(key=lambda m: m["combined_score"], reverse=True)

    return final_matches


def dedupe_reviewed_matches(matches, overlap_thresh):
    if not matches:
        return []

    boxes = [m["bbox"] for m in matches]
    scores = [m["combined_score"] for m in matches]
    keep_idx = non_max_suppression(boxes, scores, overlap_thresh=overlap_thresh)

    deduped = [matches[i] for i in keep_idx]
    deduped.sort(key=lambda m: m["combined_score"], reverse=True)
    return deduped