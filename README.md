# Motasport Pattern Generator

Flask app that generates Hawaiian shirt mockups using Grok API, applies them to garment images with multiply blend masking, uploads to WordPress, and exports WooCommerce-ready CSVs.

---

## Deploy to Vercel via GitHub

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/motasport-app.git
git push -u origin main
```

### 2. Import to Vercel

1. Go to [vercel.com](https://vercel.com) → **Add New Project**
2. Import your GitHub repo
3. Framework: **Other**
4. Click **Deploy** — Vercel auto-detects `vercel.json`

### 3. Set Environment Variables in Vercel

In Vercel dashboard → Project → **Settings → Environment Variables**, add:

| Key | Value |
|-----|-------|
| `GROK_API_KEY` | `xai-ApoeBxVH...` |
| `WP_BASE_URL` | `https://motasport.com` |
| `WP_USERNAME` | `admin` |
| `WP_APP_PASS` | `O0kK pqnZ 6GCx SoJN 4Ru0 YLKh` |

> ⚠️ Never hardcode secrets in code — always use environment variables.

### 4. Redeploy

After adding env vars, go to **Deployments → Redeploy** to pick them up.

---

## API Endpoints

### `GET /`
Web UI — single prompt form + CSV batch uploader.

### `GET /api/health`
Check if env vars are set correctly.
```json
{ "status": "ok", "grok_key_set": true, "wp_pass_set": true }
```

### `POST /api/generate`
Single prompt → generate → upload → return URLs.

**Request:**
```json
{
  "prompt": "Tropical hibiscus flowers...",
  "title": "Sunset Hibiscus Pattern",
  "description": "Optional product description"
}
```

**Response:**
```json
{
  "sku": "A3K-9XZ",
  "name": "Sunset Hibiscus Pattern",
  "urls": ["https://motasport.com/.../mockup_front.jpg", "..."],
  "images_field": "https://..., https://...",
  "product_url": "https://motasport.com/product/sunset-hibiscus-pattern/"
}
```

### `POST /api/generate-csv`
CSV batch → process all prompts → download WooCommerce-ready CSV.

**Request:** `multipart/form-data` with `file` = CSV file
(columns: `pattern_prompt`, `title`, `description`)

**Response:** `output_wc.csv` file download
(WooCommerce import format with `Prompt` column appended)

---

## Run Locally

```bash
pip install -r requirements.txt

export GROK_API_KEY="xai-..."
export WP_BASE_URL="https://motasport.com"
export WP_USERNAME="admin"
export WP_APP_PASS="O0kK pqnZ ..."

python app.py
# Open http://localhost:5000
```

---

## CSV Format

Input CSV must have:
| Column | Required | Description |
|--------|----------|-------------|
| `pattern_prompt` | ✅ | Prompt sent to Grok image API |
| `title` | ✅ | WooCommerce product name |
| `description` | ❌ | HTML product description |

Output `output_wc.csv` has all 43 WooCommerce columns + `Prompt` at the end — ready to import directly.
