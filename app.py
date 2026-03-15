import os, csv, base64, time, random, string, io, json, requests
from flask import Flask, render_template, request, Response, jsonify, send_file
from PIL import Image
import numpy as np
from io import BytesIO
from scipy.ndimage import binary_fill_holes, label as nd_label

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB upload limit

# ── Garment image URLs ──────────────────────────────────────────────────────
GARMENT_IMAGES = [
    "https://motasport.com/wp-content/uploads/2026/03/colar_front.jpeg",
    "https://motasport.com/wp-content/uploads/2026/03/fabric.jpeg",
    "https://motasport.com/wp-content/uploads/2026/03/front.jpeg",
    "https://motasport.com/wp-content/uploads/2026/03/pocket.jpeg",
    "https://motasport.com/wp-content/uploads/2026/03/sleeve.jpeg",
    "https://motasport.com/wp-content/uploads/2026/03/tidy.jpeg",
    "https://motasport.com/wp-content/uploads/2026/03/back.jpeg",
    "https://motasport.com/wp-content/uploads/2026/03/colar_back.jpeg",
]
GARMENT_LABELS = ["collar_front", "fabric", "front", "pocket", "sleeve", "tidy", "back", "collar_back"]

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

CHARS = string.ascii_uppercase + string.digits

def random_sku():
    return "".join(random.choices(CHARS, k=3)) + "-" + "".join(random.choices(CHARS, k=3))

def load_image_from_url(src):
    r = requests.get(src, timeout=30)
    r.raise_for_status()
    return Image.open(BytesIO(r.content)).convert("RGBA")

def generate_pattern(api_key, prompt):
    resp = requests.post(
        "https://api.x.ai/v1/images/generations",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": "grok-2-image", "prompt": prompt, "n": 1, "response_format": "b64_json"},
        timeout=120
    )
    result = resp.json()
    if "error" in result:
        raise RuntimeError(f"Grok API error: {result['error']}")
    d = result["data"][0]
    if "b64_json" in d:
        img_bytes = base64.b64decode(d["b64_json"])
    else:
        img_bytes = requests.get(d["url"], timeout=60).content
    return Image.open(BytesIO(img_bytes)).convert("RGBA")

def build_shirt_mask(arr):
    if not np.all(arr[:, :, 3] == 255):
        return arr[:, :, 3] > 10
    rgb = arr[:, :, :3]
    is_white = np.all(rgb >= 245, axis=2)
    labeled, _ = nd_label(is_white)
    border = np.zeros_like(is_white)
    border[0, :] = is_white[0, :]; border[-1, :] = is_white[-1, :]
    border[:, 0] = is_white[:, 0]; border[:, -1] = is_white[:, -1]
    bg_labels = set(labeled[border].flatten()) - {0}
    return binary_fill_holes(~np.isin(labeled, list(bg_labels)))

def apply_pattern(garment_img, pattern_img):
    arr  = np.array(garment_img)
    mask = build_shirt_mask(arr)
    pat  = pattern_img.resize(garment_img.size, Image.LANCZOS).convert("RGB")
    g    = np.array(garment_img.convert("RGB")).astype(np.float32) / 255.0
    lum  = 0.299 * g[:, :, 0] + 0.587 * g[:, :, 1] + 0.114 * g[:, :, 2]
    lm   = np.clip(lum / (lum[mask].mean() if mask.any() else 0.85), 0.3, 1.4)
    blend = np.clip(np.array(pat).astype(np.float32) / 255.0 * lm[:, :, np.newaxis], 0, 1)
    alpha = (mask * 255).astype(np.uint8)
    result = Image.fromarray(np.dstack([(blend * 255).astype(np.uint8), alpha]), "RGBA")
    bg = Image.new("RGBA", garment_img.size, (255, 255, 255, 255))
    bg.paste(result, mask=result)
    buf = BytesIO()
    bg.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()

def upload_to_wordpress(wp_url, wp_user, wp_pass, file_bytes, filename):
    resp = requests.post(
        f"{wp_url.rstrip('/')}/wp-json/wp/v2/media",
        auth=(wp_user, wp_pass),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "image/png",
        },
        data=file_bytes,
        timeout=60
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Upload failed ({resp.status_code}): {resp.text[:200]}")
    return resp.json()["source_url"]

# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/run", methods=["POST"])
def run_pipeline():
    # ── collect form data ──
    grok_api_key = request.form.get("grok_api_key", "").strip()
    wp_url       = request.form.get("wp_url", "").strip()
    wp_user      = request.form.get("wp_user", "").strip()
    wp_pass      = request.form.get("wp_pass", "").strip()
    regular_price = request.form.get("regular_price", "32.99").strip()
    category     = request.form.get("category", "Urban Edge").strip()

    csv_file = request.files.get("csv_file")
    if not grok_api_key:
        return jsonify(error="Grok API key is required."), 400
    if not csv_file:
        return jsonify(error="Please upload a prompts CSV file."), 400

    csv_content = csv_file.read().decode("utf-8")
    prompt_rows = list(csv.DictReader(io.StringIO(csv_content)))
    if not prompt_rows:
        return jsonify(error="CSV file is empty or invalid."), 400

    WC_DEFAULTS = {
        "Type": "simple", "Published": "1", "Is featured?": "0",
        "Visibility in catalog": "visible", "Tax status": "taxable", "Tax class": "",
        "In stock?": "1", "Stock": "", "Low stock amount": "", "Backorders allowed?": "0",
        "Sold individually?": "0", "Weight (kg)": "", "Length (cm)": "",
        "Width (cm)": "", "Height (cm)": "", "Allow customer reviews?": "1",
        "Purchase note": "", "Sale price": "", "Regular price": regular_price,
        "Categories": category, "Tags": "", "Shipping class": "",
        "Download limit": "", "Download expiry days": "", "Parent": "",
        "Grouped products": "", "Upsells": "", "Cross-sells": "",
        "External URL": "", "Button text": "", "Position": "0",
        "WCPA Forms": "0", "Brands": "", "GTIN, UPC, EAN, or ISBN": "",
        "Short description": "", "Date sale price starts": "", "Date sale price ends": "",
    }

    def stream():
        output_rows = []
        total = len(prompt_rows)

        def sse(event, data):
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        yield sse("start", {"total": total})

        # Load garments once
        yield sse("log", {"msg": "⏳ Loading garment images..."})
        garments = []
        for src, label in zip(GARMENT_IMAGES, GARMENT_LABELS):
            try:
                img = load_image_from_url(src)
                garments.append((label, img))
            except Exception as e:
                yield sse("error", {"msg": f"Failed to load garment {label}: {e}"})
                return
        yield sse("log", {"msg": f"✅ {len(garments)} garments loaded."})

        for row_idx, row in enumerate(prompt_rows):
            prompt      = row.get("pattern_prompt", "").strip()
            title       = row.get("title", f"Pattern {row_idx+1}")
            description = row.get("description", "")
            safe_title  = "".join(c if c.isalnum() else "_" for c in title)[:35]

            yield sse("progress", {"row": row_idx + 1, "total": total, "title": title})
            yield sse("log", {"msg": f"🎨 [{row_idx+1}/{total}] Generating pattern for: {title}"})

            # Generate pattern
            try:
                pattern = generate_pattern(grok_api_key, prompt)
                yield sse("log", {"msg": f"   ✅ Pattern generated ({pattern.size[0]}×{pattern.size[1]})"})
            except Exception as e:
                yield sse("error", {"msg": f"   ❌ Pattern generation failed: {e}"})
                return

            # Apply + upload
            uploaded_urls = []
            for g_idx, (label, garment_img) in enumerate(garments):
                out_filename = f"mockup_{row_idx+1:02d}_{safe_title}_{label}.png"
                try:
                    file_bytes = apply_pattern(garment_img, pattern)
                    yield sse("log", {"msg": f"   🖼  [{g_idx+1}/{len(garments)}] Uploading {label}..."})
                    if wp_url and wp_user and wp_pass:
                        url = upload_to_wordpress(wp_url, wp_user, wp_pass, file_bytes, out_filename)
                        uploaded_urls.append(url)
                        yield sse("log", {"msg": f"      ✅ Uploaded: {url.split('/')[-1]}"})
                    else:
                        uploaded_urls.append(f"[no-wp]{out_filename}")
                        yield sse("log", {"msg": f"      ⚠️  No WP creds — skipped upload for {label}"})
                except Exception as e:
                    yield sse("log", {"msg": f"      ❌ Failed {label}: {e}"})

            # Build WC row
            sku = random_sku()
            product_slug = title.lower().replace(" ", "-").replace(",", "")[:60]
            wc_row = {col: "" for col in WC_COLUMNS}
            wc_row.update(WC_DEFAULTS)
            wc_row.update({
                "ID": "", "SKU": sku, "Name": title,
                "Description": description,
                "Images": ", ".join(uploaded_urls),
                "Product URL": f"{wp_url.rstrip('/')}/product/{product_slug}/" if wp_url else "",
                "Prompt": prompt,
            })
            output_rows.append(wc_row)
            yield sse("log", {"msg": f"   ✅ Done. SKU={sku} | {len(uploaded_urls)} images"})

            if row_idx < total - 1:
                time.sleep(1)

        # Build CSV in memory
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=WC_COLUMNS)
        writer.writeheader()
        writer.writerows(output_rows)
        csv_data = buf.getvalue()

        yield sse("done", {"csv": csv_data, "rows": len(output_rows)})

    return Response(stream(), mimetype="text/event-stream",
                    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


if __name__ == "__main__":
    app.run(debug=True)
