import base64, os
from PIL import Image
from io import BytesIO

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

SUPPORTED = {".jpg", ".jpeg", ".png", ".jfif", ".webp", ".bmp", ".heic", ".heif", ".tiff", ".tif", ".avif", ".gif", ".pdf"}
MAX_PX = 4096


def load_pdf(path: str) -> list[dict]:
    """Convert each page of a PDF to a JPEG image and return list of dicts."""
    import fitz  # PyMuPDF
    doc = fitz.open(path)
    results = []
    base_name = os.path.splitext(os.path.basename(path))[0]
    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(dpi=200)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        w, h = img.size
        if max(w, h) > MAX_PX:
            ratio = MAX_PX / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=90)
        b64 = base64.b64encode(buf.getvalue()).decode()
        page_name = f"{base_name}_page{i}.jpg"
        results.append({"file": page_name, "path": path, "image_b64": b64})
    doc.close()
    return results


def load_image(path: str) -> dict | list[dict]:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return load_pdf(path)
    img = Image.open(path).convert("RGB")
    w, h = img.size
    if max(w, h) > MAX_PX:
        ratio = MAX_PX / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=90)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return {"file": os.path.basename(path), "path": path, "image_b64": b64}


def load_folder(folder: str) -> list[dict]:
    images = []
    for f in sorted(os.listdir(folder)):
        if os.path.splitext(f)[1].lower() in SUPPORTED:
            images.append(load_image(os.path.join(folder, f)))
    return images
