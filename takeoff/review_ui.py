from pathlib import Path
import cv2
import numpy as np


_review_click_result = None
_review_buttons = {}


def review_mouse_callback(event, x, y, flags, param):
    global _review_click_result, _review_buttons

    if event != cv2.EVENT_LBUTTONDOWN:
        return

    for name, (x1, y1, x2, y2) in _review_buttons.items():
        if x1 <= x <= x2 and y1 <= y <= y2:
            _review_click_result = name
            return


def build_review_canvas(template_path: Path, search_region_path: Path, bbox, symbol_name: str,
                        candidate_info=None, review_index=None, review_total=None):
    template_img = cv2.imread(str(template_path))
    search_img = cv2.imread(str(search_region_path))

    if template_img is None:
        raise RuntimeError(f"Could not read template image: {template_path}")
    if search_img is None:
        raise RuntimeError(f"Could not read search image: {search_region_path}")

    x1, y1, x2, y2 = bbox
    candidate = search_img[y1:y2, x1:x2]

    if candidate.size == 0:
        raise RuntimeError("Candidate crop was empty.")

    def resize_keep_aspect(img, target_h):
        h, w = img.shape[:2]
        if h <= 0 or w <= 0:
            return img
        scale = target_h / h
        new_w = max(1, int(round(w * scale)))
        return cv2.resize(img, (new_w, target_h), interpolation=cv2.INTER_NEAREST)

    panel_h = 260
    template_disp = resize_keep_aspect(template_img, panel_h)
    candidate_disp = resize_keep_aspect(candidate, panel_h)

    label_h = 35
    gap = 30
    side_pad = 20
    top_pad = 20
    bottom_pad = 120

    left_panel_w = template_disp.shape[1]
    right_panel_w = candidate_disp.shape[1]

    canvas_w = side_pad + left_panel_w + gap + right_panel_w + side_pad
    canvas_h = top_pad + label_h + panel_h + bottom_pad

    canvas = np.full((canvas_h, canvas_w, 3), 245, dtype=np.uint8)

    left_x = side_pad
    right_x = side_pad + left_panel_w + gap
    img_y = top_pad + label_h

    header_text = f"{symbol_name} Candidate Review"
    cv2.putText(canvas, header_text, (side_pad, 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 20), 2, cv2.LINE_AA)

    cv2.putText(canvas, "Template", (left_x, top_pad + 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (20, 20, 20), 2, cv2.LINE_AA)
    cv2.putText(canvas, "Candidate", (right_x, top_pad + 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (20, 20, 20), 2, cv2.LINE_AA)

    canvas[img_y:img_y + template_disp.shape[0], left_x:left_x + template_disp.shape[1]] = template_disp
    canvas[img_y:img_y + candidate_disp.shape[0], right_x:right_x + candidate_disp.shape[1]] = candidate_disp

    info_y = img_y + panel_h + 25
    if candidate_info:
        text = (
            f"Combined: {candidate_info['combined_score']:.3f}   "
            f"Binary: {candidate_info['binary_score']:.3f}   "
            f"Edge: {candidate_info['edge_score']:.3f}   "
            f"IoU: {candidate_info['iou_score']:.3f}"
        )
        cv2.putText(canvas, text, (side_pad, info_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.58, (40, 40, 40), 1, cv2.LINE_AA)

    if review_index is not None and review_total is not None:
        review_text = f"Candidate {review_index} of {review_total}"
        cv2.putText(canvas, review_text, (side_pad, info_y + 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.58, (40, 40, 40), 1, cv2.LINE_AA)

    button_y1 = canvas_h - 55
    button_y2 = canvas_h - 15
    button_w = 140
    button_gap = 20

    total_button_width = button_w * 3 + button_gap * 2
    start_x = (canvas_w - total_button_width) // 2

    accept_box = (start_x, button_y1, start_x + button_w, button_y2)
    reject_box = (start_x + button_w + button_gap, button_y1,
                  start_x + 2 * button_w + button_gap, button_y2)
    quit_box = (start_x + 2 * (button_w + button_gap), button_y1,
                start_x + 3 * button_w + 2 * button_gap, button_y2)

    cv2.rectangle(canvas, (accept_box[0], accept_box[1]), (accept_box[2], accept_box[3]), (60, 180, 75), -1)
    cv2.rectangle(canvas, (reject_box[0], reject_box[1]), (reject_box[2], reject_box[3]), (60, 60, 220), -1)
    cv2.rectangle(canvas, (quit_box[0], quit_box[1]), (quit_box[2], quit_box[3]), (120, 120, 120), -1)

    cv2.putText(canvas, "Accept", (accept_box[0] + 28, accept_box[1] + 27),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(canvas, "Reject", (reject_box[0] + 28, reject_box[1] + 27),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(canvas, "Quit", (quit_box[0] + 40, quit_box[1] + 27),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

    buttons = {
        "accepted": accept_box,
        "rejected": reject_box,
        "quit": quit_box
    }

    return canvas, buttons


def review_candidate_with_buttons(template_path: Path, search_region_path: Path, cand, symbol_name: str,
                                  window_name: str, review_index=None, review_total=None):
    global _review_click_result, _review_buttons

    _review_click_result = None

    canvas, buttons = build_review_canvas(
        template_path,
        search_region_path,
        cand["bbox"],
        symbol_name=symbol_name,
        candidate_info=cand,
        review_index=review_index,
        review_total=review_total
    )
    _review_buttons = buttons

    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(window_name, review_mouse_callback)

    while True:
        cv2.imshow(window_name, canvas)
        key = cv2.waitKey(20) & 0xFF

        try:
            visible = cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE)
            if visible < 1:
                return "quit"
        except cv2.error:
            return "quit"

        if _review_click_result is not None:
            result = _review_click_result
            _review_click_result = None
            return result

        if key == ord("y"):
            return "accepted"
        elif key == ord("n"):
            return "rejected"
        elif key == ord("q") or key == 27:
            return "quit"


def triage_candidates_for_review(scored_candidates, config):
    auto_accept = []
    auto_reject = []
    uncertain = []

    for cand in scored_candidates:
        combined = cand["combined_score"]
        iou = cand["iou_score"]

        if combined >= config.auto_accept_score and iou >= config.review_iou_floor:
            cand["decision_source"] = "auto_accept"
            auto_accept.append(cand)
        elif combined <= config.auto_reject_score:
            cand["decision_source"] = "auto_reject"
            auto_reject.append(cand)
        else:
            cand["decision_source"] = "user_review"
            uncertain.append(cand)

    return auto_accept, auto_reject, uncertain


def review_uncertain_candidates(template_path: Path, search_region_path: Path, uncertain_candidates,
                                symbol_name: str, config):
    accepted = []
    rejected = []

    print("\n===== USER REVIEW FOR UNCERTAIN CANDIDATES =====")
    print("Use the review window buttons:")
    print("  Accept = count it")
    print("  Reject = discard it")
    print("  Quit   = stop review")
    print("Keyboard shortcuts also work: y / n / q")
    print("===============================================\n")

    total = len(uncertain_candidates)

    for i, cand in enumerate(uncertain_candidates, start=1):
        print(f"Reviewing candidate {i}/{total}")

        result = review_candidate_with_buttons(
            template_path,
            search_region_path,
            cand,
            symbol_name=symbol_name,
            window_name=config.review_window_name,
            review_index=i,
            review_total=total
        )

        if result == "accepted":
            cand["user_review"] = "accepted"
            accepted.append(cand)
        elif result == "rejected":
            cand["user_review"] = "rejected"
            rejected.append(cand)
        elif result == "quit":
            cv2.destroyAllWindows()
            print("User stopped review early.")
            return accepted, rejected, True

    cv2.destroyAllWindows()
    return accepted, rejected, False