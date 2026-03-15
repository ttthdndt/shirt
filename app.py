import os
import csv
import base64
import random
import string
import io
import requests
import numpy as np
from PIL import Image
from flask import Flask, request, jsonify, render_template, send_file
from collections import deque

app = Flask(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
GROK_API_KEY = os.environ.get("GROK_API_KEY", "")
WP_BASE_URL  = os.environ.get("WP_BASE_URL",  "https://motasport.com")
WP_USERNAME  = os.environ.get("WP_USERNAME",  "admin")
WP_APP_PASS  = os.environ.get("WP_APP_PASS",  "")

GARMENT_URLS = [
    "https://motasport.com/wp-content/uploads/2026/03/colar_front.jpeg",
    "https://motasport.com/wp-content/uploads/2026/03/fabric.jpeg",
    "https://motasport.com/wp-content/uploads/2026/03/front.jpeg",
    "https://motasport.com/wp-content/uploads/2026/03/pocket.jpeg",
    "https://motasport.com/wp-content/uploads/2026/03/sleeve.jpeg",
    "https://motasport.com/wp-content/uploads/2026/03/tidy.jpeg",
    "https://motasport.com/wp-content/uploads/2026/03/back.jpeg",
    "https://motasport.com/wp-content/uploads/2026/03/colar_back.jpeg",
]
GARMENT_LABELS = [
    "collar_front", "fabric", "front", "pocket",
    "sleeve", "tidy", "back", "collar_back"
]

WC_COLUMNS = [
    "ID", "Type", "SKU", "GTIN, UPC, EAN, or ISBN", "Name",
    "Published", "Is featured?", "Visibility in catalog",
    "Short description", "Description",
    "Date sale price starts", "Date sale price ends",
    "Tax status", "Tax class", "In stock?", "Stock",
    "Low stock amount", "Backorders allowed?", "Sold individually?",
    "Weight (kg)", "Length (cm)", "Width (cm)", "Height (cm)",
    "Allow customer reviews?", "Purchase note",
    "Sale price", "Regular price",
    "Categories", "Tags", "Shipping class",
    "Images",
    "Download limit", "Download expiry days",
    "Parent", "Grouped products", "Upsells", "Cross-sells",
    "External URL", "Button text", "Position",
    "WCPA Forms", "Brands", "Product URL",
    "Prompt",
]

WC_DEFAULTS = {
    "Type": "simple", "Published": "1", "Is featured?": "0",
    "Visibility in catalog": "visible", "Tax status": "taxable",
    "Tax class": "", "In stock?": "1", "Stock": "",
    "Low stock amount": "", "Backorders allowed?": "0",
    "Sold individually?": "0", "Weight (kg)": "", "Length (cm)": "",
    "Width (cm)": "", "Height (cm)": "", "Allow customer reviews?": "1",
    "Purchase note": "", "Sale price": "", "Regular price": "32.99",
    "Categories": "Urban Edge", "Tags": "", "Shipping class": "",
    "Download limit": "", "Download expiry days": "", "Parent": "",
    "Grouped products": "", "Upsells": "", "Cross-sells": "",
    "External URL": "", "Button text": "", "Position": "0",
    "WCPA Forms": "0", "Brands": "",
    "GTIN, UPC, EAN, or ISBN": "", "Short description": "",
    "Date sale price starts": "", "Date sale price ends": "",
}

# ── Image cache (in-memory, per instance) ────────────────────────────────────
_garment_cache = {}


# ── Helper: SKU ───────────────────────────────────────────────────────────────
def random_sku():
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=3)) + "-" + "".join(random.choices(chars, k=3))


# ── Helper: load image from URL ───────────────────────────────────────────────
def fetch_image(url):
    if url in _garment_cache:
        return _garment_cache[url].copy()
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
    _garment_cache[url] = img
    return img.copy()


# ── Helper: shirt mask (BFS flood fill, no scipy) ────────────────────────────
def build_shirt_mask(arr):
    """Returns boolean mask: True = shirt, False = background."""
    # If image has real transparency, use alpha channel directly
    if not np.all(arr[:, :, 3] == 255):
        return arr[:, :, 3] > 10

    h, w = arr.shape[:2]
    rgb = arr[:, :, :3]
    is_white = np.all(rgb >= 245, axis=2)

    # BFS from all 4 border white pixels to find background
    visited = np.zeros((h, w), dtype=bool)
    queue = deque()

    for y in range(h):
        for x in [0, w - 1]:
            if is_white[y, x] and not visited[y, x]:
                visited[y, x] = True
                queue.append((y, x))
    for x in range(w):
        for y in [0, h - 1]:
            if is_white[y, x] and not visited[y, x]:
                visited[y, x] = True
                queue.append((y, x))

    while queue:
        cy, cx = queue.popleft()
        for dy, dx in [(-1,0),(1,0),(0,-1),(0,1)]:
            ny, nx = cy+dy, cx+dx
            if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx] and is_white[ny, nx]:
                visited[ny, nx] = True
                queue.append((ny, nx))

    shirt_mask = ~visited

    # Fill holes inside shirt (collar gap, etc.) using second BFS from border non-shirt
    # Any remaining background = exterior; invert to get solid shirt shape
    not_shirt = ~shirt_mask
    exterior = np.zeros((h, w), dtype=bool)
    border_q = deque()
    for y in range(h):
        for x in [0, w-1]:
            if not_shirt[y, x] and not exterior[y, x]:
                exterior[y, x] = True
                border_q.append((y, x))
    for x in range(w):
        for y in [0, h-1]:
            if not_shirt[y, x] and not exterior[y, x]:
                exterior[y, x] = True
                border_q.append((y, x))
    while border_q:
        cy, cx = border_q.popleft()
        for dy, dx in [(-1,0),(1,0),(0,-1),(0,1)]:
            ny, nx = cy+dy, cx+dx
            if 0 <= ny < h and 0 <= nx < w and not exterior[ny, nx] and not_shirt[ny, nx]:
                exterior[ny, nx] = True
                border_q.append((ny, nx))

    return ~exterior


# ── Helper: apply pattern with multiply blend ─────────────────────────────────
def apply_pattern(garment_img, pattern_img):
    """Returns composited PIL Image (pattern blended onto garment shape)."""
    arr  = np.array(garment_img)
    mask = build_shirt_mask(arr)
    pat  = pattern_img.resize(garment_img.size, Image.LANCZOS).convert("RGB")
    g    = np.array(garment_img.convert("RGB")).astype(np.float32) / 255.0
    lum  = 0.299*g[:,:,0] + 0.587*g[:,:,1] + 0.114*g[:,:,2]
    lm   = np.clip(lum / (lum[mask].mean() if mask.any() else 0.85), 0.3, 1.4)
    blend = np.clip(np.array(pat).astype(np.float32)/255.0 * lm[:,:,np.newaxis], 0, 1)
    alpha = (mask * 255).astype(np.uint8)
    result = Image.fromarray(np.dstack([(blend*255).astype(np.uint8), alpha]), "RGBA")
    bg = Image.new("RGBA", garment_img.size, (255,255,255,255))
    bg.paste(result, mask=result)
    return bg


# ── Helper: generate pattern from Grok ───────────────────────────────────────
def generate_pattern(prompt):
    resp = requests.post(
        "https://api.x.ai/v1/images/generations",
        headers={"Authorization": f"Bearer {GROK_API_KEY}", "Content-Type": "application/json"},
        json={"model": "grok-2-image-1212", "prompt": prompt, "n": 1, "response_format": "b64_json"},
        timeout=60
    )
    result = resp.json()
    if "error" in result:
        raise RuntimeError(f"Grok API error: {result['error']}")
    img_bytes = base64.b64decode(result["data"][0]["b64_json"]) \
        if "b64_json" in result["data"][0] \
        else requests.get(result["data"][0]["url"]).content
    return Image.open(io.BytesIO(img_bytes)).convert("RGBA")


# ── Helper: upload to WordPress ───────────────────────────────────────────────
def upload_to_wordpress(img, filename):
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=90)
    buf.seek(0)
    resp = requests.post(
        f"{WP_BASE_URL.rstrip('/')}/wp-json/wp/v2/media",
        auth=(WP_USERNAME, WP_APP_PASS),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "image/jpeg",
        },
        data=buf.read(),
        timeout=60
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"WP upload failed ({resp.status_code}): {resp.text[:200]}")
    return resp.json()["source_url"]


# ── Core pipeline for one prompt ─────────────────────────────────────────────
def process_prompt(prompt, title, description=""):
    safe = "".join(c if c.isalnum() else "_" for c in title)[:35]

    # 1. Generate pattern
    pattern = generate_pattern(prompt)

    # 2. Apply to each garment + upload
    uploaded_urls = []
    for label, garment_url in zip(GARMENT_LABELS, GARMENT_URLS):
        garment_img = fetch_image(garment_url)
        result_img  = apply_pattern(garment_img, pattern)
        filename    = f"mockup_{safe}_{label}.jpg"
        url = upload_to_wordpress(result_img, filename)
        uploaded_urls.append(url)

    # 3. Build WC row
    sku = random_sku()
    slug = title.lower().replace(" ", "-")[:60]
    wc_row = {col: "" for col in WC_COLUMNS}
    wc_row.update(WC_DEFAULTS)
    wc_row.update({
        "ID":          "",
        "SKU":         sku,
        "Name":        title,
        "Description": description,
        "Images":      ", ".join(uploaded_urls),
        "Product URL": f"{WP_BASE_URL}/product/{slug}/",
        "Prompt":      prompt,
    })
    return wc_row, uploaded_urls


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """
    Single prompt endpoint.
    Body: { "prompt": "...", "title": "...", "description": "..." }
    Returns: { "sku": "...", "urls": [...], "images_field": "..." }
    """
    data = request.get_json()
    if not data or "prompt" not in data:
        return jsonify({"error": "Missing 'prompt' field"}), 400

    prompt      = data["prompt"].strip()
    title       = data.get("title", "Hawaiian Shirt Pattern")
    description = data.get("description", "")

    try:
        wc_row, urls = process_prompt(prompt, title, description)
        return jsonify({
            "sku":          wc_row["SKU"],
            "name":         wc_row["Name"],
            "urls":         urls,
            "images_field": wc_row["Images"],
            "product_url":  wc_row["Product URL"],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/generate-csv", methods=["POST"])
def api_generate_csv():
    """
    CSV batch endpoint.
    Accepts multipart/form-data with 'file' = CSV (columns: pattern_prompt, title, description).
    Returns: CSV file download with WC columns + Prompt.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    content = file.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)

    if not rows:
        return jsonify({"error": "CSV is empty"}), 400
    if "pattern_prompt" not in rows[0]:
        return jsonify({"error": "CSV must have a 'pattern_prompt' column"}), 400

    output_rows = []
    errors = []

    for i, row in enumerate(rows):
        prompt      = row.get("pattern_prompt", "").strip()
        title       = row.get("title", f"Pattern {i+1}")
        description = row.get("description", "")

        if not prompt:
            errors.append(f"Row {i+1}: empty prompt, skipped")
            continue

        try:
            wc_row, _ = process_prompt(prompt, title, description)
            output_rows.append(wc_row)
        except Exception as e:
            errors.append(f"Row {i+1} ({title}): {str(e)}")

    # Build output CSV in memory
    out_buf = io.StringIO()
    writer = csv.DictWriter(out_buf, fieldnames=WC_COLUMNS)
    writer.writeheader()
    writer.writerows(output_rows)
    out_buf.seek(0)

    bytes_buf = io.BytesIO(("\ufeff" + out_buf.getvalue()).encode("utf-8"))
    bytes_buf.seek(0)

    response = send_file(
        bytes_buf,
        mimetype="text/csv",
        as_attachment=True,
        download_name="output_wc.csv"
    )
    if errors:
        response.headers["X-Processing-Errors"] = " | ".join(errors)
    return response


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "wp_base_url": WP_BASE_URL,
        "grok_key_set": bool(GROK_API_KEY),
        "wp_pass_set": bool(WP_APP_PASS),
    })


if __name__ == "__main__":
    app.run(debug=True)
