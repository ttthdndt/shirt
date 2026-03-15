import os
import time
from config import OUTPUT_FOLDER, WP_BASE_URL, WC_COLUMNS, WC_DEFAULTS
from helpers import generate_pattern, upload_to_wordpress, random_sku
from image_processing import apply_pattern


def _timer(log, label, start):
    elapsed = time.time() - start
    log(f"    ⏱ {label}: {elapsed:.2f}s")
    return elapsed


def run_pipeline(prompt_rows, garments, job, api_key=None):
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    output_rows = []
    total = len(prompt_rows)

    pipeline_start = time.time()

    for row_idx, row in enumerate(prompt_rows):
        if job.cancelled:
            job.log("Job cancelled by user.")
            break

        prompt      = row["pattern_prompt"].strip()
        title       = row.get("title", f"Pattern {row_idx + 1}").strip()
        description = row.get("description", "").strip()
        safe_title  = "".join(c if c.isalnum() else "_" for c in title)[:35]

        prompt_start = time.time()
        job.log(f"")
        job.log(f"── [{row_idx + 1}/{total}] {title}")
        job.set_progress(row_idx * 2, total * 2)

        # ── 1. Generate pattern ───────────────────────────────────────────────
        job.log("  Generating pattern via Grok API...")
        job.status_detail = "generating"
        t = time.time()
        try:
            pattern = generate_pattern(prompt, api_key=api_key, log=job.log)
        except Exception as e:
            job.log(f"  ❌ Generation failed: {e}")
            job.status    = "error"
            job.error_msg = str(e)
            return output_rows
        _timer(job.log, "Grok API", t)

        if job.cancelled:
            job.log("  Cancelled after generation.")
            break

        t = time.time()
        pattern_path = os.path.join(OUTPUT_FOLDER, f"pattern_{row_idx+1:02d}_{safe_title}.png")
        pattern.save(pattern_path)
        _timer(job.log, "Save pattern PNG", t)

        job.set_progress(row_idx * 2 + 1, total * 2)
        job.status_detail = "uploading"

        # ── 2. Apply + upload ─────────────────────────────────────────────────
        uploaded_urls = []
        total_mask_time   = 0.0
        total_upload_time = 0.0

        for g_idx, (label, garment_img) in enumerate(garments):
            if job.cancelled:
                job.log("  Cancelled during upload.")
                break

            out_filename = f"mockup_{row_idx+1:02d}_{safe_title}_{label}.png"
            out_path     = os.path.join(OUTPUT_FOLDER, out_filename)

            job.log(f"  [{g_idx+1}/{len(garments)}] {label}")

            # Masking
            t = time.time()
            apply_pattern(garment_img, pattern, out_path, log=job.log)
            mask_time = time.time() - t
            total_mask_time += mask_time
            job.log(f"    ⏱ Mask+blend: {mask_time:.2f}s")

            # Upload
            t = time.time()
            try:
                url = upload_to_wordpress(
                    out_path, out_filename,
                    log=job.log,
                    retries=3,
                    retry_delay=5,
                )
                upload_time = time.time() - t
                total_upload_time += upload_time
                uploaded_urls.append(url)
                job.log(f"    ⏱ Upload: {upload_time:.2f}s  →  {url}")
            except Exception as e:
                upload_time = time.time() - t
                total_upload_time += upload_time
                job.log(f"    ⏱ Upload: {upload_time:.2f}s  ❌ Failed after retries: {e}")

        if job.cancelled:
            break

        # ── 3. WooCommerce row ────────────────────────────────────────────────
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

        prompt_total = time.time() - prompt_start
        job.set_progress((row_idx + 1) * 2, total * 2)
        job.log(f"")
        job.log(f"  ── Timing summary for [{row_idx+1}/{total}] {title}")
        job.log(f"     Masking  (×{len(garments)}): {total_mask_time:.2f}s  avg {total_mask_time/len(garments):.2f}s/garment")
        job.log(f"     Uploads  (×{len(uploaded_urls)}): {total_upload_time:.2f}s  avg {total_upload_time/max(len(uploaded_urls),1):.2f}s/upload")
        job.log(f"     Prompt total: {prompt_total:.2f}s  |  SKU: {wc_row['SKU']}")

    pipeline_total = time.time() - pipeline_start
    job.set_progress(total * 2, total * 2)
    job.status_detail = ""
    job.log(f"")
    job.log(f"══ Pipeline finished in {pipeline_total:.1f}s ({pipeline_total/60:.1f} min) ══")
    return output_rows
