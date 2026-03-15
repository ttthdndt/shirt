# 👕 Grok Shirt Pattern Generator

A Flask web app that:
1. Reads prompts from a CSV
2. Generates seamless patterns via the **Grok (xAI) API**
3. Applies patterns to garment images (mask + multiply blend)
4. Uploads results to **WordPress / WooCommerce**
5. Outputs a ready-to-import `output_wc.csv`

---

## 🚀 Deploy to Vercel via GitHub

### Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
# Create a repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/grok-shirt-app.git
git push -u origin main
```

### Step 2 — Deploy on Vercel

1. Go to [vercel.com](https://vercel.com) → **Add New Project**
2. Import your GitHub repository
3. Vercel auto-detects Python — click **Deploy**
4. Done! Your app is live at `https://your-app.vercel.app`

> **Note:** Vercel Pro gives 300s max function duration. For large CSV files (10+ prompts), consider running locally with `python app.py` instead.

---

## 💻 Run Locally

```bash
pip install -r requirements.txt
python app.py
# Open http://localhost:5000
```

---

## 📄 CSV Format

Your upload must have these columns:

| Column | Description |
|--------|-------------|
| `pattern_prompt` | The prompt sent to Grok image API |
| `title` | WooCommerce product title |
| `description` | Product description (long) |

See `prompts_sample.csv` for an example.

---

## ⚙️ UI Fields

| Field | Required | Description |
|-------|----------|-------------|
| Grok API Key | ✅ | Your `xai-…` key from [console.x.ai](https://console.x.ai) |
| WordPress URL | Optional | e.g. `https://yourstore.com` |
| WP Username | Optional | WordPress admin username |
| App Password | Optional | WordPress Application Password |
| Regular Price | Optional | Default `32.99` |
| Category | Optional | Default `Urban Edge` |
