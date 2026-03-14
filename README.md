# Shirt Pattern Generator — WooCommerce Pipeline

Flask web app that takes a CSV of prompts, generates patterns via Grok API,
masks them onto garment images, uploads to WordPress, and outputs a
WooCommerce-ready CSV.

## File structure

| File | Purpose |
|------|---------|
| `config.py` | All config: API keys, WP credentials, WC columns, garment URLs |
| `validator.py` | CSV upload + column validation (reports missing/extra columns) |
| `garment_downloader.py` | Downloads garment images from URLs, caches locally |
| `helpers.py` | `generate_pattern()`, `upload_to_wordpress()`, `random_sku()` |
| `image_processing.py` | `build_shirt_mask()`, `apply_pattern()` (multiply blend) |
| `pipeline.py` | Main loop: prompt → generate → mask → upload |
| `csv_writer.py` | Serialize output rows to WooCommerce CSV |
| `app.py` | Flask routes + background job management |
| `templates/index.html` | Web UI |

## Local setup

```bash
git clone https://github.com/YOUR_USERNAME/shirt-pipeline
cd shirt-pipeline
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
python app.py
# open http://localhost:5000
```

## Deploy to Vercel

### 1. Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/shirt-pipeline.git
git push -u origin main
```

### 2. Import on Vercel
1. Go to [vercel.com](https://vercel.com) → **Add New Project**
2. Import your GitHub repo
3. Framework: **Other**
4. Add Environment Variables (from `.env.example`):
   - `GROK_API_KEY`
   - `WP_BASE_URL`
   - `WP_USERNAME`
   - `WP_APP_PASS`
   - `SECRET_KEY`
5. Click **Deploy**

> ⚠️ **Vercel timeout note:** Vercel Hobby has a 10s function timeout; Pro has 60s.
> For large CSV batches (many prompts), consider deploying on your Contabo VPS instead:
> ```bash
> gunicorn -w 2 -b 0.0.0.0:5000 app:app
> ```

## Input CSV format

| Column | Required | Description |
|--------|----------|-------------|
| `pattern_prompt` | ✅ | Prompt sent to Grok image API |
| `title` | ✅ | WooCommerce product name |
| `description` | ✅ | WooCommerce product description |

## Output CSV

WooCommerce-ready — all 43 standard WC import columns in correct order,
plus `Prompt` appended at the end. Ready to import at:
**WooCommerce → Products → Import**.
