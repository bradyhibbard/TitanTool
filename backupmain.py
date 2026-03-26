from openai import OpenAI
import fitz
import base64
import json
import re
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw
from key import OPENAI_API_KEY

# ============================================================
# Config
# ============================================================

client = OpenAI(api_key=OPENAI_API_KEY)

PDF_PATH = "house_plans.pdf"
PAGE_INDEX = 4  # page 5 (0-based)
MODEL_NAME = "gpt-5.4"

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

DEBUG_CANDIDATE_DIR = OUTPUT_DIR / "candidate_debug"
DEBUG_CANDIDATE_DIR.mkdir(exist_ok=True)

PAGE_IMG_PATH = OUTPUT_DIR / "page5.png"
LEGEND_CROP_PATH = OUTPUT_DIR / "electrical_legend_crop.png"
BATH_FAN_SYMBOL_CROP_PATH = OUTPUT_DIR / "bath_fan_symbol_crop.png"
SEARCH_REGION_PATH = OUTPUT_DIR / "page5_search_region.png"
DEBUG_MATCHES_PATH = OUTPUT_DIR / "page5_bath_fan_matches.png"
RESULT_JSON_PATH = OUTPUT_DIR / "page5_bath_fan_count.json"

PREPROC_TEMPLATE_BINARY_PATH = OUTPUT_DIR / "debug_template_binary.png"
PREPROC_TEMPLATE_EDGES_PATH = OUTPUT_DIR / "debug_template_edges.png"
PREPROC_SEARCH_BINARY_PATH = OUTPUT_DIR / "debug_search_binary.png"
PREPROC_SEARCH_EDGES_PATH = OUTPUT_DIR / "debug_search_edges.png"

DEBUG_GROUPED_MASK_PATH = OUTPUT_DIR / "debug_grouped_mask.png"
DEBUG_PROPOSALS_PATH = OUTPUT_DIR / "debug_candidate_proposals.png"

# Rendering / preprocessing
RENDER_ZOOM = 2.0
MANUAL_TEMPLATE_BORDER_PX = 6

# Proposal generation
PROPOSAL_SCALES = (0.85, 0.95, 1.0, 1.05, 1.15)
FINAL_SCALES = (0.90, 1.00, 1.10)
EDGE_PROPOSAL_THRESHOLD = 0.32
MAX_EDGE_PROPOSALS_PER_SCALE = 60

# Final scoring
FINAL_ACCEPT_SCORE = 0.50
FINAL_MIN_BINARY_SCORE = 0.20
FINAL_MIN_EDGE_SCORE = 0.10
FINAL_MIN_IOU_SCORE = 0.12
MIN_CENTER_DISTANCE_FACTOR = 0.45
NMS_OVERLAP_THRESH = 0.20

# User review logic
ENABLE_USER_REVIEW = True
AUTO_ACCEPT_SCORE = 0.72
AUTO_REJECT_SCORE = 0.38
REVIEW_IOU_FLOOR = 0.08
MAX_UNCERTAIN_TO_REVIEW = 20

SAVE_TOP_CANDIDATE_CROPS = 30

# ============================================================
# Utility functions
# ============================================================

def render_pdf_page(pdf_path: str, page_index: int, out_path: Path, zoom: float = 2.0) -> Path:
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    pix.save(str(out_path))
    return out_path


def encode_image_to_base64(img_path: Path) -> str:
    with open(img_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError(f"Could not parse JSON from model output:\n{text}")


def ask_model_for_json(image_path: Path, prompt: str, model: str = MODEL_NAME):
    b64 = encode_image_to_base64(image_path)

    response = client.responses.create(
        model=model,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt},
                {
                    "type": "input_image",
                    "image_url": f"data:image/png;base64,{b64}",
                    "detail": "high"
                }
            ]
        }]
    )

    raw = response.output_text.strip()
    print("\n--- MODEL RAW OUTPUT ---")
    print(raw)
    print("--- END OUTPUT ---\n")

    return extract_json(raw)


def normalized_bbox_to_pixels(bbox_0_to_999, width, height):
    x1_n, y1_n, x2_n, y2_n = bbox_0_to_999

    x1 = max(0, min(width - 1, int(x1_n / 999 * width)))
    y1 = max(0, min(height - 1, int(y1_n / 999 * height)))
    x2 = max(0, min(width, int(x2_n / 999 * width)))
    y2 = max(0, min(height, int(y2_n / 999 * height)))

    if x2 <= x1:
        x2 = min(width, x1 + 1)
    if y2 <= y1:
        y2 = min(height, y1 + 1)

    return x1, y1, x2, y2


def expand_bbox(x1, y1, x2, y2, width, height, pad=20):
    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(width, x2 + pad)
    y2 = min(height, y2 + pad)
    return x1, y1, x2, y2


def crop_image(img_path: Path, bbox_px, out_path: Path) -> Path:
    img = Image.open(img_path)
    crop = img.crop(bbox_px)
    crop.save(out_path)
    return out_path


def clip_box(x1, y1, x2, y2, w, h):
    x1 = max(0, min(w - 1, int(round(x1))))
    y1 = max(0, min(h - 1, int(round(y1))))
    x2 = max(0, min(w, int(round(x2))))
    y2 = max(0, min(h, int(round(y2))))

    if x2 <= x1:
        x2 = min(w, x1 + 1)
    if y2 <= y1:
        y2 = min(h, y1 + 1)

    return x1, y1, x2, y2


def add_white_border(img_bgr, border_px=6):
    return cv2.copyMakeBorder(
        img_bgr,
        border_px, border_px, border_px, border_px,
        cv2.BORDER_CONSTANT,
        value=(255, 255, 255)
    )


def manually_crop_symbol(image_path: Path, output_path: Path, border_px: int = 6):
    img = cv2.imread(str(image_path))
    if img is None:
        raise RuntimeError(f"Could not read image for manual cropping: {image_path}")

    print("\nManual crop step:")
    print("- Drag a tight box around ONLY the bath fan symbol")
    print("- Do NOT include label text or table/grid lines")
    print("- Press ENTER or SPACE to confirm\n")

    roi = cv2.selectROI("Select Bath Fan Symbol", img, showCrosshair=True, fromCenter=False)
    cv2.destroyAllWindows()

    x, y, w, h = roi
    if w <= 0 or h <= 0:
        raise RuntimeError("No crop selected. Please run again and select the bath fan symbol.")

    crop = img[y:y+h, x:x+w]
    crop = add_white_border(crop, border_px=border_px)

    cv2.imwrite(str(output_path), crop)

    print(f"Saved manual symbol crop to: {output_path}")
    print(f"Manual crop bbox within legend image: {(x, y, x + w, y + h)}")
    print(f"Added white border around template: {border_px}px")

    return (x, y, x + w, y + h)


def preprocess_variants(img_bgr):
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray_blur = cv2.GaussianBlur(gray, (3, 3), 0)

    _, binary = cv2.threshold(
        gray_blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )

    edges = cv2.Canny(gray_blur, 50, 150)

    grouped = cv2.dilate(binary, np.ones((3, 3), np.uint8), iterations=1)
    grouped = cv2.morphologyEx(grouped, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)

    return {
        "gray": gray,
        "binary": binary,
        "edges": edges,
        "grouped": grouped
    }


def save_preprocessed_debug(image_path: Path, binary_out: Path, edges_out: Path):
    img = cv2.imread(str(image_path))
    if img is None:
        raise RuntimeError(f"Could not read image for preprocessing debug: {image_path}")
    proc = preprocess_variants(img)
    cv2.imwrite(str(binary_out), proc["binary"])
    cv2.imwrite(str(edges_out), proc["edges"])


def build_search_region_image(page_img_path: Path, plan_bbox_px, legend_bbox_px, out_path: Path):
    img = Image.open(page_img_path).convert("RGB")

    result = Image.new("RGB", img.size, (255, 255, 255))
    plan_crop = img.crop(plan_bbox_px)
    result.paste(plan_crop, (plan_bbox_px[0], plan_bbox_px[1]))

    draw = ImageDraw.Draw(result)
    lx1, ly1, lx2, ly2 = legend_bbox_px
    draw.rectangle([lx1, ly1, lx2, ly2], fill=(255, 255, 255))

    result.save(out_path)
    return out_path


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


def draw_boxes(image_path: Path, boxes, out_path: Path, color=(255, 0, 0), labels=None):
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    for i, box in enumerate(boxes):
        x1, y1, x2, y2 = box
        draw.rectangle([x1, y1, x2, y2], outline=color, width=2)
        if labels and i < len(labels):
            draw.text((x1, max(0, y1 - 14)), str(labels[i]), fill=color)

    img.save(out_path)
    return out_path


def save_candidate_crop(search_bgr, bbox, out_path: Path):
    x1, y1, x2, y2 = bbox
    crop = search_bgr[y1:y2, x1:x2]
    if crop.size > 0:
        cv2.imwrite(str(out_path), crop)


# ============================================================
# Proposal generation
# ============================================================

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
        ys, xs = np.where(result >= threshold)

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


# ============================================================
# Candidate scoring
# ============================================================

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


def filter_and_dedupe_initial_matches(scored_matches, template_w, template_h):
    if not scored_matches:
        return []

    kept = []
    for m in scored_matches:
        if m["combined_score"] < FINAL_ACCEPT_SCORE:
            continue
        if m["binary_score"] < FINAL_MIN_BINARY_SCORE:
            continue
        if m["edge_score"] < FINAL_MIN_EDGE_SCORE:
            continue
        if m["iou_score"] < FINAL_MIN_IOU_SCORE:
            continue
        kept.append(m)

    if not kept:
        return []

    kept.sort(key=lambda m: m["combined_score"], reverse=True)

    min_center_distance = max(12, int(round(max(template_w, template_h) * MIN_CENTER_DISTANCE_FACTOR)))
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
    keep_idx = non_max_suppression(boxes, scores, overlap_thresh=NMS_OVERLAP_THRESH)

    final_matches = [center_kept[i] for i in keep_idx]
    final_matches.sort(key=lambda m: m["combined_score"], reverse=True)

    return final_matches


# ============================================================
# User review
# ============================================================

def show_candidate_review(template_path: Path, search_region_path: Path, bbox, window_name="Review Candidate"):
    template_img = cv2.imread(str(template_path))
    search_img = cv2.imread(str(search_region_path))

    if template_img is None:
        raise RuntimeError(f"Could not read template image: {template_path}")
    if search_img is None:
        raise RuntimeError(f"Could not read search image: {search_region_path}")

    x1, y1, x2, y2 = bbox
    candidate = search_img[y1:y2, x1:x2]

    if candidate.size == 0:
        return None

    max_h = 220

    def resize_keep_aspect(img, target_h):
        h, w = img.shape[:2]
        if h <= 0 or w <= 0:
            return img
        scale = target_h / h
        new_w = max(1, int(round(w * scale)))
        return cv2.resize(img, (new_w, target_h), interpolation=cv2.INTER_NEAREST)

    template_disp = resize_keep_aspect(template_img, max_h)
    candidate_disp = resize_keep_aspect(candidate, max_h)

    label_h = 30
    template_canvas = np.full((template_disp.shape[0] + label_h, template_disp.shape[1], 3), 255, dtype=np.uint8)
    candidate_canvas = np.full((candidate_disp.shape[0] + label_h, candidate_disp.shape[1], 3), 255, dtype=np.uint8)

    template_canvas[label_h:, :] = template_disp
    candidate_canvas[label_h:, :] = candidate_disp

    cv2.putText(template_canvas, "Template", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(candidate_canvas, "Candidate", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)

    gap = 20
    total_h = max(template_canvas.shape[0], candidate_canvas.shape[0])
    total_w = template_canvas.shape[1] + gap + candidate_canvas.shape[1]

    combined = np.full((total_h, total_w, 3), 240, dtype=np.uint8)
    combined[:template_canvas.shape[0], :template_canvas.shape[1]] = template_canvas
    combined[:candidate_canvas.shape[0], template_canvas.shape[1] + gap:] = candidate_canvas

    cv2.imshow(window_name, combined)
    return combined


def triage_candidates_for_review(scored_candidates):
    auto_accept = []
    auto_reject = []
    uncertain = []

    for cand in scored_candidates:
        combined = cand["combined_score"]
        iou = cand["iou_score"]

        if combined >= AUTO_ACCEPT_SCORE and iou >= REVIEW_IOU_FLOOR:
            cand["decision_source"] = "auto_accept"
            auto_accept.append(cand)
        elif combined <= AUTO_REJECT_SCORE:
            cand["decision_source"] = "auto_reject"
            auto_reject.append(cand)
        else:
            cand["decision_source"] = "user_review"
            uncertain.append(cand)

    return auto_accept, auto_reject, uncertain


def review_uncertain_candidates(template_path: Path, search_region_path: Path, uncertain_candidates):
    accepted = []
    rejected = []

    print("\n===== USER REVIEW FOR UNCERTAIN CANDIDATES =====")
    print("Type:")
    print("  y = yes, this is a bath fan")
    print("  n = no, discard it")
    print("  q = quit review early")
    print("===============================================\n")

    for i, cand in enumerate(uncertain_candidates, start=1):
        bbox = cand["bbox"]

        show_candidate_review(template_path, search_region_path, bbox, window_name="Bath Fan Candidate Review")

        print(f"\nCandidate {i}/{len(uncertain_candidates)}")
        print(f"Combined: {cand['combined_score']:.3f}")
        print(f"Binary:   {cand['binary_score']:.3f}")
        print(f"Edge:     {cand['edge_score']:.3f}")
        print(f"IoU:      {cand['iou_score']:.3f}")
        print(f"BBox:     {cand['bbox']}")

        while True:
            user_input = input("Is this a bath fan symbol? (y/n/q): ").strip().lower()

            if user_input == "y":
                cand["user_review"] = "accepted"
                accepted.append(cand)
                break
            elif user_input == "n":
                cand["user_review"] = "rejected"
                rejected.append(cand)
                break
            elif user_input == "q":
                cv2.destroyAllWindows()
                print("User stopped review early.")
                return accepted, rejected, True
            else:
                print("Please enter y, n, or q.")

    cv2.destroyAllWindows()
    return accepted, rejected, False


def dedupe_reviewed_matches(matches):
    if not matches:
        return []

    boxes = [m["bbox"] for m in matches]
    scores = [m["combined_score"] for m in matches]
    keep_idx = non_max_suppression(boxes, scores, overlap_thresh=NMS_OVERLAP_THRESH)

    deduped = [matches[i] for i in keep_idx]
    deduped.sort(key=lambda m: m["combined_score"], reverse=True)
    return deduped


# ============================================================
# Detection
# ============================================================

def detect_symbol_candidates(search_region_path: Path, template_path: Path):
    search_bgr = cv2.imread(str(search_region_path))
    template_bgr = cv2.imread(str(template_path))

    if search_bgr is None:
        raise RuntimeError(f"Could not read search region image: {search_region_path}")
    if template_bgr is None:
        raise RuntimeError(f"Could not read template image: {template_path}")

    search_proc = preprocess_variants(search_bgr)
    template_proc = preprocess_variants(template_bgr)

    cv2.imwrite(str(DEBUG_GROUPED_MASK_PATH), search_proc["grouped"])

    template_h, template_w = template_proc["binary"].shape[:2]

    contour_proposals = generate_contour_proposals(
        search_proc["grouped"],
        template_w=template_w,
        template_h=template_h,
        candidate_scales=FINAL_SCALES
    )

    edge_proposals = generate_edge_match_proposals(
        search_proc["edges"],
        template_proc["edges"],
        scales=PROPOSAL_SCALES,
        threshold=EDGE_PROPOSAL_THRESHOLD,
        max_per_scale=MAX_EDGE_PROPOSALS_PER_SCALE
    )

    all_proposals = contour_proposals + edge_proposals
    all_proposals = dedupe_proposals(all_proposals, overlap_thresh=0.25)

    proposal_boxes = [p["bbox"] for p in all_proposals]
    proposal_labels = [f'{p["source"]}:{round(p["proposal_score"], 2)}' for p in all_proposals]
    draw_boxes(search_region_path, proposal_boxes, DEBUG_PROPOSALS_PATH, color=(0, 0, 255), labels=proposal_labels)

    scored = []
    for prop in all_proposals:
        result = score_candidate(search_bgr, template_proc, prop["bbox"])
        if result is None:
            continue

        result["proposal_source"] = prop["source"]
        result["proposal_scale"] = prop["scale"]
        result["proposal_score"] = float(prop["proposal_score"])
        scored.append(result)

    scored.sort(key=lambda m: m["combined_score"], reverse=True)

    for i, m in enumerate(scored[:SAVE_TOP_CANDIDATE_CROPS], start=1):
        crop_name = (
            f"{i:02d}_score_{m['combined_score']:.3f}"
            f"_bin_{m['binary_score']:.3f}"
            f"_edge_{m['edge_score']:.3f}"
            f"_iou_{m['iou_score']:.3f}.png"
        )
        save_candidate_crop(search_bgr, m["bbox"], DEBUG_CANDIDATE_DIR / crop_name)

    initial_matches = filter_and_dedupe_initial_matches(scored, template_w, template_h)

    return {
        "initial_matches": initial_matches,
        "all_scored_candidates": scored,
        "proposal_count": len(all_proposals),
        "template_size": {
            "width": template_w,
            "height": template_h
        }
    }


# ============================================================
# Debug drawing
# ============================================================

def save_debug_matches(image_path: Path, matches, out_path: Path):
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
# Prompts
# ============================================================

LEGEND_PROMPT = """
You are analyzing a residential construction drawing.

Task:
Find the ELECTRICAL SYMBOLS legend on this page.

Instructions:
1. Look for a table, boxed region, or grouped region that contains electrical labels and matching symbols.
2. Return the bounding box for the FULL electrical legend region.
3. Be generous enough to include the title and all rows of the legend.
4. If there are multiple legends, choose the one specifically related to electrical symbols.
5. Return ONLY valid JSON.

Output format:
{
  "found": true,
  "legend_type": "electrical_symbols",
  "bbox_0_to_999": [x_min, y_min, x_max, y_max],
  "confidence": 0.0,
  "reason": "short reason"
}
"""

PLAN_REGION_PROMPT = """
You are analyzing a residential construction drawing page.

Task:
Find the main house plan / floor plan drawing area in the center of the page.

Instructions:
1. Identify the large central drawing region that contains the actual house plan linework.
2. Do NOT include page margins, notes, title blocks, legends, or schedules unless they overlap the drawing itself.
3. Return one bounding box for the main plan region only.
4. Return ONLY valid JSON.

Output format:
{
  "found": true,
  "region_type": "main_house_plan",
  "bbox_0_to_999": [x_min, y_min, x_max, y_max],
  "confidence": 0.0,
  "reason": "short reason"
}
"""


# ============================================================
# Main pipeline
# ============================================================

def main():
    render_pdf_page(PDF_PATH, PAGE_INDEX, PAGE_IMG_PATH, zoom=RENDER_ZOOM)
    print(f"Saved rendered page to: {PAGE_IMG_PATH}")

    page_img = Image.open(PAGE_IMG_PATH)
    page_w, page_h = page_img.size

    legend_data = ask_model_for_json(PAGE_IMG_PATH, LEGEND_PROMPT)
    if not legend_data.get("found", False):
        raise RuntimeError("Electrical legend was not found.")

    legend_bbox_px = normalized_bbox_to_pixels(
        legend_data["bbox_0_to_999"], page_w, page_h
    )
    legend_bbox_px = expand_bbox(*legend_bbox_px, page_w, page_h, pad=25)

    crop_image(PAGE_IMG_PATH, legend_bbox_px, LEGEND_CROP_PATH)
    print(f"Saved legend crop to: {LEGEND_CROP_PATH}")
    print(f"Legend pixel bbox on page: {legend_bbox_px}")

    plan_data = ask_model_for_json(PAGE_IMG_PATH, PLAN_REGION_PROMPT)
    if not plan_data.get("found", False):
        raise RuntimeError("Main house plan region was not found.")

    plan_bbox_px = normalized_bbox_to_pixels(
        plan_data["bbox_0_to_999"], page_w, page_h
    )
    plan_bbox_px = expand_bbox(*plan_bbox_px, page_w, page_h, pad=10)

    print(f"Plan search region pixel bbox on page: {plan_bbox_px}")

    manual_symbol_bbox = manually_crop_symbol(
        LEGEND_CROP_PATH,
        BATH_FAN_SYMBOL_CROP_PATH,
        border_px=MANUAL_TEMPLATE_BORDER_PX
    )

    build_search_region_image(PAGE_IMG_PATH, plan_bbox_px, legend_bbox_px, SEARCH_REGION_PATH)
    print(f"Saved search-region image to: {SEARCH_REGION_PATH}")

    save_preprocessed_debug(
        BATH_FAN_SYMBOL_CROP_PATH,
        PREPROC_TEMPLATE_BINARY_PATH,
        PREPROC_TEMPLATE_EDGES_PATH
    )
    save_preprocessed_debug(
        SEARCH_REGION_PATH,
        PREPROC_SEARCH_BINARY_PATH,
        PREPROC_SEARCH_EDGES_PATH
    )

    print(f"Saved preprocessed template binary debug to: {PREPROC_TEMPLATE_BINARY_PATH}")
    print(f"Saved preprocessed template edges debug to: {PREPROC_TEMPLATE_EDGES_PATH}")
    print(f"Saved preprocessed search binary debug to: {PREPROC_SEARCH_BINARY_PATH}")
    print(f"Saved preprocessed search edges debug to: {PREPROC_SEARCH_EDGES_PATH}")

    detection = detect_symbol_candidates(
        SEARCH_REGION_PATH,
        BATH_FAN_SYMBOL_CROP_PATH
    )

    initial_matches = detection["initial_matches"]

    if ENABLE_USER_REVIEW:
        auto_accept, auto_reject, uncertain = triage_candidates_for_review(initial_matches)

        uncertain.sort(key=lambda c: abs(c["combined_score"] - AUTO_ACCEPT_SCORE))
        uncertain = uncertain[:MAX_UNCERTAIN_TO_REVIEW]

        print(f"\nAuto-accepted: {len(auto_accept)}")
        print(f"Auto-rejected: {len(auto_reject)}")
        print(f"Needs review:  {len(uncertain)}")

        reviewed_accept, reviewed_reject, review_stopped = review_uncertain_candidates(
            BATH_FAN_SYMBOL_CROP_PATH,
            SEARCH_REGION_PATH,
            uncertain
        )

        matches = auto_accept + reviewed_accept
        matches = dedupe_reviewed_matches(matches)

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

    save_debug_matches(SEARCH_REGION_PATH, matches, DEBUG_MATCHES_PATH)
    print(f"Saved debug match image to: {DEBUG_MATCHES_PATH}")

    result = {
        "page_index": PAGE_INDEX,
        "page_number": PAGE_INDEX + 1,
        "legend_bbox_px_on_page": legend_bbox_px,
        "plan_bbox_px_on_page": plan_bbox_px,
        "manual_symbol_bbox_within_legend": manual_symbol_bbox,
        "match_count_inside_plan_outside_legend": len(matches),
        "proposal_count": detection["proposal_count"],
        "template_size": detection["template_size"],
        "review_summary": review_summary,
        "matches": matches,
        "top_scored_candidates_preview": detection["all_scored_candidates"][:20],
        "parameters": {
            "render_zoom": RENDER_ZOOM,
            "manual_template_border_px": MANUAL_TEMPLATE_BORDER_PX,
            "proposal_scales": PROPOSAL_SCALES,
            "final_scales": FINAL_SCALES,
            "edge_proposal_threshold": EDGE_PROPOSAL_THRESHOLD,
            "max_edge_proposals_per_scale": MAX_EDGE_PROPOSALS_PER_SCALE,
            "final_accept_score": FINAL_ACCEPT_SCORE,
            "final_min_binary_score": FINAL_MIN_BINARY_SCORE,
            "final_min_edge_score": FINAL_MIN_EDGE_SCORE,
            "final_min_iou_score": FINAL_MIN_IOU_SCORE,
            "min_center_distance_factor": MIN_CENTER_DISTANCE_FACTOR,
            "nms_overlap_thresh": NMS_OVERLAP_THRESH,
            "enable_user_review": ENABLE_USER_REVIEW,
            "auto_accept_score": AUTO_ACCEPT_SCORE,
            "auto_reject_score": AUTO_REJECT_SCORE,
            "review_iou_floor": REVIEW_IOU_FLOOR,
            "max_uncertain_to_review": MAX_UNCERTAIN_TO_REVIEW
        },
        "files": {
            "page_image": str(PAGE_IMG_PATH),
            "legend_crop": str(LEGEND_CROP_PATH),
            "bath_fan_symbol_crop": str(BATH_FAN_SYMBOL_CROP_PATH),
            "search_region_image": str(SEARCH_REGION_PATH),
            "debug_matches": str(DEBUG_MATCHES_PATH),
            "preprocessed_template_binary": str(PREPROC_TEMPLATE_BINARY_PATH),
            "preprocessed_template_edges": str(PREPROC_TEMPLATE_EDGES_PATH),
            "preprocessed_search_binary": str(PREPROC_SEARCH_BINARY_PATH),
            "preprocessed_search_edges": str(PREPROC_SEARCH_EDGES_PATH),
            "grouped_mask": str(DEBUG_GROUPED_MASK_PATH),
            "candidate_proposals_overlay": str(DEBUG_PROPOSALS_PATH),
            "candidate_debug_dir": str(DEBUG_CANDIDATE_DIR)
        }
    }

    with open(RESULT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print("\n========== RESULT ==========")
    print(f"Bath fan count on page {PAGE_INDEX + 1} inside main plan and outside legend: {len(matches)}")
    print(f"Proposal count: {detection['proposal_count']}")
    print(f"Saved result JSON to: {RESULT_JSON_PATH}")
    print("============================\n")


if __name__ == "__main__":
    main()