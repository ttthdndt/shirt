import os
import time
from config import OUTPUT_FOLDER, WP_BASE_URL, WC_COLUMNS, WC_DEFAULTS
from helpers import generate_pattern, upload_to_wordpress, random_sku
from image_processing import apply_pattern


def run_pipeline(prompt_rows, garments, job, api_key=None):
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    output_rows = []
    total = len(prompt_rows)

    for row_idx, row in enumerate(prompt_rows):
        if job.cancelled:
            job.log("Job cancelled by user.")
            break

        prompt      = row["pattern_prompt"].strip()
        title       = row.get("title", f"Pattern {row_idx + 1}").strip()
        description = row.get("description", "").strip()
        safe_title  = "".join(c if c.isalnum() else "_" for c in title)[:35]

        job.log(f"")
        job.log(f"── [{row_idx + 1}/{total}] {title}")
        job.set_progress(row_idx * 2, total * 2)  # each prompt = 2 units (generate + upload)

        # ── 1. Generate pattern via Grok ─────────────────────────────────────
        job.log(f"  Generating pattern via Grok API...")
        job.log(f"  ⏳ This may take 30–60 seconds, please wait...")
        job.status_detail = "generating"

        pattern = generate_pattern(prompt, api_key=api_key)

        if job.cancelled:
            job.log("  Cancelled after generation — skipping upload.")
            break

        pattern_path = os.path.join(OUTPUT_FOLDER, f"pattern_{row_idx+1:02d}_{safe_title}.png")
        pattern.save(pattern_path)
        job.log(f"  ✓ Pattern generated & saved.")
        job.set_progress(row_idx * 2 + 1, total * 2)
        job.status_detail = "uploading"

        # ── 2. Apply to all garments + upload ─────────────────────────────────
        uploaded_urls = []
        for g_idx, (label, garment_img) in enumerate(garments):
            if job.cancelled:
                job.log("  Cancelled during upload.")
                break

            out_filename = f"mockup_{row_idx+1:02d}_{safe_title}_{label}.png"
            out_path     = os.path.join(OUTPUT_FOLDER, out_filename)

            job.log(f"  [{g_idx+1}/{len(garments)}] {label} — masking + uploading...")
            apply_pattern(garment_img, pattern, out_path)
            url = upload_to_wordpress(out_path, out_filename)
            uploaded_urls.append(url)
            job.log(f"    ✓ {url}")

        if job.cancelled:
            break

        # ── 3. Build WooCommerce row ──────────────────────────────────────────
        product_slug = title.lower().replace(" ", "-").replace(",", "")[:60]
        wc_row = {col: "" for col in WC_COLUMNS}
        wc_row.update(WC_DEFAULTS)
        wc_row.update({
            "ID":          "",
            "SKU":         random_sku(),
            "Name":        title,
            "Description": description,
            "Images":      ", ".join(uploaded_urls),
            "Product URL": f"{WP_BASE_URL.rstrip('/')}/product/{product_slug}/",
            "Prompt":      prompt,
        })
        output_rows.append(wc_row)

        job.set_progress((row_idx + 1) * 2, total * 2)
        job.log(f"  ✓ Done — {len(uploaded_urls)} images uploaded | SKU: {wc_row['SKU']}")

    job.set_progress(total * 2, total * 2)
    job.status_detail = ""
    return output_rows
