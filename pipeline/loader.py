import base64, os
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from io import BytesIO

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

SUPPORTED = {".jpg", ".jpeg", ".png", ".jfif", ".webp", ".bmp", ".heic", ".heif", ".tiff", ".tif", ".avif", ".gif", ".pdf"}
MAX_PX = 4096


def _gps_to_decimal(gps_info):
    """Convert GPS EXIF to decimal degrees."""
    def _convert(value):
        d, m, s = value
        return float(d) + float(m)/60 + float(s)/3600

    lat = _convert(gps_info.get(2, (0, 0, 0)))
    lng = _convert(gps_info.get(4, (0, 0, 0)))
    if gps_info.get(1) == 'S':
        lat = -lat
    if gps_info.get(3) == 'W':
        lng = -lng
    return lat, lng


def extract_exif(path: str) -> dict:
    """Extract EXIF metadata from an image file."""
    meta = {
        "gps_lat": None,
        "gps_lng": None,
        "date_taken": None,
        "camera_make": None,
        "camera_model": None,
        "width": None,
        "height": None,
        "orientation": None,
        "file_size_kb": round(os.path.getsize(path) / 1024, 1) if os.path.isfile(path) else None,
    }
    try:
        img = Image.open(path)
        meta["width"], meta["height"] = img.size

        exif_data = img.getexif()
        if not exif_data:
            return meta

        # Build tag name lookup
        tag_map = {}
        for tag_id, value in exif_data.items():
            tag_name = TAGS.get(tag_id, tag_id)
            tag_map[tag_name] = value

        meta["date_taken"] = tag_map.get("DateTimeOriginal") or tag_map.get("DateTime")
        meta["camera_make"] = tag_map.get("Make")
        meta["camera_model"] = tag_map.get("Model")
        meta["orientation"] = tag_map.get("Orientation")

        if tag_map.get("ExifImageWidth"):
            meta["width"] = tag_map["ExifImageWidth"]
        if tag_map.get("ExifImageHeight"):
            meta["height"] = tag_map["ExifImageHeight"]

        # GPS info
        gps_ifd = exif_data.get_ifd(0x8825)
        if gps_ifd:
            try:
                lat, lng = _gps_to_decimal(gps_ifd)
                if lat != 0.0 or lng != 0.0:
                    meta["gps_lat"] = round(lat, 6)
                    meta["gps_lng"] = round(lng, 6)
            except Exception:
                pass
    except Exception:
        pass
    return meta


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


def load_image(path: str):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return load_pdf(path)
    metadata = extract_exif(path)
    img = Image.open(path).convert("RGB")
    w, h = img.size
    if max(w, h) > MAX_PX:
        ratio = MAX_PX / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=90)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return {"file": os.path.basename(path), "path": path, "image_b64": b64, "metadata": metadata}


def load_folder(folder: str) -> list[dict]:
    images = []
    for f in sorted(os.listdir(folder)):
        if os.path.splitext(f)[1].lower() in SUPPORTED:
            images.append(load_image(os.path.join(folder, f)))
    return images
