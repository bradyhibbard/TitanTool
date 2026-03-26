import fitz
from pathlib import Path


def render_pdf_page(pdf_path: str, page_index: int, out_path: Path, zoom: float = 2.0) -> Path:
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    pix.save(str(out_path))
    return out_path