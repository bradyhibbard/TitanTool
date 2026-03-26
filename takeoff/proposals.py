import cv2
from .image_utils import clip_box
from .scoring import non_max_suppression


def generate_contour_proposals(search_grouped, template_w, template_h, candidate_scales=(0.9, 1.0, 1.1)):
    h, w = search_grouped.shape[:2]
    template_area = template_w * template_h

    contours, _ = cv2.findContours(search_grouped, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    proposals = []

    min_box_area = max(8, int(template_area * 0.04))
    max_box_area = int(template_area * 5.0)

    min_w = max(3, int(template_w * 0.20))
    max_w = int(template_w * 2.40)
    min_h = max(3, int(template_h * 0.20))
    max_h = int(template_h * 2.40)

    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        area = bw * bh

        if area < min_box_area or area > max_box_area:
            continue
        if bw < min_w or bw > max_w:
            continue
        if bh < min_h or bh > max_h:
            continue

        cx = x + bw / 2.0
        cy = y + bh / 2.0

        for scale in candidate_scales:
            win_w = int(round(template_w * scale))
            win_h = int(round(template_h * scale))

            pad_x = max(3, int(round(win_w * 0.15)))
            pad_y = max(3, int(round(win_h * 0.15)))

            x1 = cx - win_w / 2.0 - pad_x
            y1 = cy - win_h / 2.0 - pad_y
            x2 = cx + win_w / 2.0 + pad_x
            y2 = cy + win_h / 2.0 + pad_y

            box = clip_box(x1, y1, x2, y2, w, h)

            proposals.append({
                "bbox": box,
                "proposal_score": 0.15,
                "source": "contour",
                "scale": scale
            })

    return proposals


def generate_edge_match_proposals(search_edges, template_edges, scales, threshold=0.32, max_per_scale=60):
    h, w = search_edges.shape[:2]
    proposals = []

    for scale in scales:
        templ = cv2.resize(
            template_edges,
            dsize=None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_LINEAR
        )
        th, tw = templ.shape[:2]

        if tw < 5 or th < 5 or tw >= w or th >= h:
            continue

        if cv2.countNonZero(templ) == 0:
            continue

        result = cv2.matchTemplate(search_edges, templ, cv2.TM_CCOEFF_NORMED)
        ys, xs = (result >= threshold).nonzero()

        scale_props = []
        for y, x in zip(ys, xs):
            score = float(result[y, x])
            box = (int(x), int(y), int(x + tw), int(y + th))
            scale_props.append({
                "bbox": box,
                "proposal_score": score,
                "source": "edge_match",
                "scale": scale
            })

        scale_props.sort(key=lambda p: p["proposal_score"], reverse=True)
        proposals.extend(scale_props[:max_per_scale])

    return proposals


def dedupe_proposals(proposals, overlap_thresh=0.25):
    if not proposals:
        return []

    boxes = [p["bbox"] for p in proposals]
    scores = [p["proposal_score"] for p in proposals]
    keep = non_max_suppression(boxes, scores, overlap_thresh=overlap_thresh)

    return [proposals[i] for i in keep]