import cv2
import numpy as np
from pathlib import Path


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