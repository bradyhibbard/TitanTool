from pathlib import Path
from PIL import Image, ImageDraw
import cv2


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


def manually_crop_symbol(image_path: Path, output_path: Path, symbol_name: str, border_px: int = 6):
    img = cv2.imread(str(image_path))
    if img is None:
        raise RuntimeError(f"Could not read image for manual cropping: {image_path}")

    print("\nManual crop step:")
    print(f"- Drag a tight box around ONLY the {symbol_name} symbol")
    print("- Do NOT include label text or table/grid lines")
    print("- Press ENTER or SPACE to confirm\n")

    roi = cv2.selectROI(f"Select {symbol_name} Symbol", img, showCrosshair=True, fromCenter=False)
    cv2.destroyAllWindows()

    x, y, w, h = roi
    if w <= 0 or h <= 0:
        raise RuntimeError(f"No crop selected. Please run again and select the {symbol_name} symbol.")

    crop = img[y:y+h, x:x+w]
    crop = add_white_border(crop, border_px=border_px)

    cv2.imwrite(str(output_path), crop)

    print(f"Saved manual symbol crop to: {output_path}")
    print(f"Manual crop bbox within legend image: {(x, y, x + w, y + h)}")
    print(f"Added white border around template: {border_px}px")

    return (x, y, x + w, y + h)


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


def save_detected_symbols(search_image_path: Path, matches, symbol_name: str, detected_symbol_dir: Path):
    img = cv2.imread(str(search_image_path))
    if img is None:
        raise RuntimeError(f"Could not read search image: {search_image_path}")

    saved_paths = []

    for i, m in enumerate(matches, start=1):
        x1, y1, x2, y2 = m["bbox"]
        crop = img[y1:y2, x1:x2]

        if crop.size == 0:
            continue

        file_name = f"{symbol_name.lower().replace(' ', '_')}_{i}.png"
        out_path = detected_symbol_dir / file_name

        cv2.imwrite(str(out_path), crop)
        saved_paths.append(str(out_path))

    return saved_paths